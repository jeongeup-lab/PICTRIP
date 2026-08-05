import renderer, { act } from "react-test-renderer";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import TravelScreen from "@/app/(tabs)/travel";
import { askAgent, type AgentAnswer, type QueryIntent } from "@/features/travel/api";
import { useNearbyCoords } from "@/features/travel/hooks/use-nearby-coords";
import { useConversation, type Turn } from "@/features/travel/stores/conversation-store";

jest.mock("expo-router", () => ({ router: { push: jest.fn(), back: jest.fn() } }));
jest.mock("react-native-safe-area-context", () => ({
  SafeAreaView: (props: { children?: unknown }) => props.children,
}));
jest.mock("@/features/travel/hooks/use-nearby-coords", () => ({ useNearbyCoords: jest.fn() }));
jest.mock("@/features/travel/usecases/pick-travel-photo", () => ({
  pickTravelPhoto: jest.fn(async () => null),
  shootTravelPhoto: jest.fn(async () => null),
}));
jest.mock("@/features/travel/api", () => ({ askAgent: jest.fn() }));
jest.mock("@/features/saved/hooks/use-save-optimistic", () => ({
  useSaveOptimistic: () => ({ saved: false, toggle: jest.fn() }),
}));
jest.mock("@/features/spots/queries", () => ({ prefetchSpot: jest.fn() }));

const { pickTravelPhoto, shootTravelPhoto } = jest.requireMock(
  "@/features/travel/usecases/pick-travel-photo",
) as {
  pickTravelPhoto: jest.Mock;
  shootTravelPhoto: jest.Mock;
};
const askAgentMock = askAgent as jest.Mock;
const useNearbyCoordsMock = useNearbyCoords as jest.Mock;

const COORDS = { lat: 37.5665, lng: 126.978 };

const INTENT: QueryIntent = {
  categoryKeywords: ["계곡"],
  regionHints: [],
  crowdPreference: "quiet",
  indoorOnly: false,
  nearMe: false,
};

const ANSWER: AgentAnswer = {
  steps: [{ tool: "category_search", label: "계곡 관광지 조회", badge: "12곳" }],
  answer: [{ text: "조건에 맞는 곳으로 4곳 추렸어요", emphasis: false }],
  spots: [],
  totalCount: 4,
  intent: INTENT,
  suggestions: ["실내만"],
  refinements: [{ label: "실내만", patch: { indoorOnly: true } }],
};

const answeredTurn: Turn = {
  id: "seed-1",
  question: "여름에 시원한 계곡",
  request: "여름에 시원한 계곡",
  photo: null,
  status: "done",
  answer: ANSWER,
  errorMessage: null,
  intent: null,
  patch: null,
  anchor: null,
  context: null,
};

const NEWER_INTENT: QueryIntent = {
  categoryKeywords: ["박물관"],
  regionHints: ["부산"],
  crowdPreference: "any",
  indoorOnly: false,
  nearMe: false,
};

const newerAnsweredTurn: Turn = {
  id: "seed-2",
  question: "부산 박물관",
  request: "부산 박물관",
  photo: null,
  status: "done",
  answer: {
    ...ANSWER,
    intent: NEWER_INTENT,
    suggestions: ["사람 적은 곳만"],
    refinements: [{ label: "사람 적은 곳만", patch: { crowdPreference: "quiet" } }],
  },
  errorMessage: null,
  intent: null,
  patch: null,
  anchor: null,
  context: null,
};

const legacyAnsweredTurn: Turn = {
  id: "seed-4",
  question: "여름에 시원한 계곡",
  request: "여름에 시원한 계곡",
  photo: null,
  status: "done",
  answer: { ...ANSWER, suggestions: ["실내만"], refinements: undefined },
  errorMessage: null,
  intent: null,
  patch: null,
  anchor: null,
  context: null,
};

const relabeledTurn: Turn = {
  ...answeredTurn,
  id: "seed-5",
  answer: {
    ...ANSWER,
    suggestions: ["사람 적은 곳만"],
    refinements: [{ label: "실내만", patch: { indoorOnly: true } }],
  },
};

const failedRefineTurn: Turn = {
  id: "seed-3",
  question: "실내만",
  request: "",
  photo: null,
  status: "failed",
  answer: null,
  errorMessage: "답을 만들지 못했어요.",
  intent: INTENT,
  patch: { indoorOnly: true },
  anchor: null,
  context: null,
};

let mounted: renderer.ReactTestRenderer | null = null;
let client: QueryClient;

beforeEach(() => {
  jest.clearAllMocks();
  useConversation.getState().clear();
  useNearbyCoordsMock.mockReturnValue({
    coords: COORDS,
    phase: "ready",
    askable: false,
    ask: jest.fn(),
  });
  askAgentMock.mockResolvedValue(ANSWER);
  client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false, gcTime: 0 },
    },
  });
});

afterEach(async () => {
  const tree = mounted;
  mounted = null;
  if (tree) await act(async () => tree.unmount());
  client.getMutationCache().clear();
  client.clear();
});

async function mount() {
  await act(async () => {
    mounted = renderer.create(
      <QueryClientProvider client={client}>
        <TravelScreen />
      </QueryClientProvider>,
    );
  });
  return mounted!;
}

function pressable(tree: renderer.ReactTestRenderer, testID: string) {
  return tree.root
    .findAllByProps({ testID })
    .find((node) => typeof node.props.onPress === "function");
}

function greeting(tree: renderer.ReactTestRenderer) {
  return tree.root
    .findAllByProps({ testID: "travel-greeting" })
    .find((node) => node.props.importantForAccessibility !== undefined)!;
}

async function press(tree: renderer.ReactTestRenderer, testID: string) {
  const node = pressable(tree, testID);
  if (!node) throw new Error(`no pressable with testID ${testID}`);
  await act(async () => node.props.onPress());
}

describe("TravelScreen empty state", () => {
  it("keeps the dock — composer and starter chips — on screen with no turns yet", async () => {
    const tree = await mount();

    expect(useConversation.getState().turns).toHaveLength(0);
    expect(greeting(tree).props.importantForAccessibility).toBe("auto");
    expect(tree.root.findAllByProps({ testID: "travel-mascot" }).length).toBeGreaterThan(0);
    expect(tree.root.findAllByProps({ testID: "travel-input" }).length).toBeGreaterThan(0);
    expect(pressable(tree, "travel-chip-근처 맛집")).toBeDefined();
  });

  it("leaves the composer in place once the first turn lands", async () => {
    const tree = await mount();
    const before = tree.root.findAllByProps({ testID: "travel-send" }).length;

    await press(tree, "travel-chip-근처 맛집");

    expect(useConversation.getState().turns).toHaveLength(1);
    expect(tree.root.findAllByProps({ testID: "travel-send" })).toHaveLength(before);
    expect(tree.root.findAllByProps({ testID: "travel-input" }).length).toBeGreaterThan(0);
    expect(greeting(tree).props.importantForAccessibility).toBe("no-hide-descendants");
  });
});

describe("TravelScreen starter chips", () => {
  it("좌표가 있으면 근처 칩이 스팟 없는 앵커로 나간다", async () => {
    const tree = await mount();
    await press(tree, "travel-chip-근처 맛집");

    expect(askAgentMock).toHaveBeenCalledTimes(1);
    const input = askAgentMock.mock.calls[0][0];
    expect(input.anchor).toEqual({ action: "food" });
    expect(input.coords).toEqual(COORDS);
    expect(input.question).toBeUndefined();
    expect(input.intent).toBeUndefined();
  });

  it("축제 칩은 준비된 intent 를 직송해 Gemini 를 건너뛴다", async () => {
    const tree = await mount();
    await press(tree, "travel-chip-지금 축제");

    const input = askAgentMock.mock.calls[0][0];
    expect(input.intent?.festivalOnly).toBe(true);
    expect(input.question).toBeUndefined();
  });

  it("좌표가 없으면 자유문 칩으로 물러난다", async () => {
    useNearbyCoordsMock.mockReturnValue({
      coords: null,
      phase: "unavailable",
      askable: false,
      ask: jest.fn(),
    });
    const tree = await mount();

    expect(pressable(tree, "travel-chip-근처 맛집")).toBeUndefined();
    await press(tree, "travel-chip-사람 적은 바닷가");

    expect(askAgentMock.mock.calls[0][0].question).toBe("사람 적은 바닷가");
  });
});

describe("TravelScreen nearby action", () => {
  it("offers the nearby pill only when a location fix exists", async () => {
    const withFix = await mount();
    expect(pressable(withFix, "travel-nearby")).toBeDefined();
    await act(async () => withFix.unmount());
    mounted = null;

    useNearbyCoordsMock.mockReturnValue({
      coords: null,
      phase: "unavailable",
      askable: false,
      ask: jest.fn(),
    });
    const withoutFix = await mount();
    expect(pressable(withoutFix, "travel-nearby")).toBeUndefined();
    expect(pressable(withoutFix, "travel-chip-사람 적은 바닷가")).toBeDefined();
  });

  it("sends the nearby pill as a free-text question", async () => {
    const tree = await mount();
    await press(tree, "travel-nearby");

    expect(askAgentMock).toHaveBeenCalledTimes(1);
    const input = askAgentMock.mock.calls[0][0];
    expect(input.question).toBe("여기서 가까운 곳");
    expect(input.patch).toBeUndefined();
    expect(input.coords).toEqual(COORDS);
  });
});

describe("TravelScreen photo attach", () => {
  it("carries the text already typed in the composer along with the photo", async () => {
    const photo = { uri: "file:///a.jpg", name: "a.jpg", type: "image/jpeg" };
    pickTravelPhoto.mockResolvedValueOnce(photo);
    const tree = await mount();
    const input = tree.root.findByProps({ testID: "travel-input" });
    await act(async () => input.props.onChangeText("제주 바다 같은 곳"));

    await press(tree, "travel-attach");
    await press(tree, "travel-send");

    expect(askAgentMock).toHaveBeenCalledTimes(1);
    const sent = askAgentMock.mock.calls[0][0];
    expect(sent.question).toBe("제주 바다 같은 곳");
    expect(sent.photo).toEqual(photo);
  });

  it("촬영한 사진도 같은 첨부 경로를 탄다", async () => {
    const shot = { uri: "file://shot.jpg", name: "shot.jpg", type: "image/jpeg" };
    shootTravelPhoto.mockResolvedValueOnce(shot);
    const tree = await mount();

    await press(tree, "travel-shoot");
    await press(tree, "travel-send");

    expect(shootTravelPhoto).toHaveBeenCalledTimes(1);
    expect(pickTravelPhoto).not.toHaveBeenCalled();
    expect(askAgentMock.mock.calls[0][0].photo).toEqual(shot);
  });

  it("카메라를 열지 못해도 앨범 첨부는 건드리지 않는다", async () => {
    shootTravelPhoto.mockRejectedValueOnce(new Error("denied"));
    const tree = await mount();

    await press(tree, "travel-shoot");

    expect(askAgentMock).not.toHaveBeenCalled();
    expect(tree.root.findByProps({ testID: "travel-attach" })).toBeTruthy();
  });
});

describe("TravelScreen new chat", () => {
  it("shows the action only once a conversation exists, and empties it", async () => {
    const empty = await mount();
    expect(pressable(empty, "travel-new-chat")).toBeUndefined();
    await act(async () => empty.unmount());
    mounted = null;

    useConversation.setState({ turns: [answeredTurn], busy: false });
    const tree = await mount();
    await press(tree, "travel-new-chat");

    expect(useConversation.getState().turns).toEqual([]);
    expect(useConversation.getState().busy).toBe(false);
    expect(tree.root.findAllByProps({ testID: "turn-seed-1" })).toHaveLength(0);
    expect(pressable(tree, "travel-chip-근처 맛집")).toBeDefined();
  });
});

describe("TravelScreen refine chips", () => {
  beforeEach(() => {
    useConversation.setState({ turns: [answeredTurn], busy: false });
  });

  it("sends the composer refine chip as intent + patch, not as text", async () => {
    const tree = await mount();
    await press(tree, "travel-chip-실내만");

    expect(askAgentMock).toHaveBeenCalledTimes(1);
    const input = askAgentMock.mock.calls[0][0];
    expect(input.patch).toEqual({ indoorOnly: true });
    expect(input.intent).toEqual(INTENT);
    expect(input.question).toBeFalsy();
  });

  it("keeps the refine turn on the transcript with its chip label as the bubble", async () => {
    const tree = await mount();
    await press(tree, "travel-chip-실내만");

    const turns = useConversation.getState().turns;
    expect(turns).toHaveLength(2);
    expect(turns[1].question).toBe("실내만");
    expect(turns[1].intent).toEqual(INTENT);
    expect(turns[1].patch).toEqual({ indoorOnly: true });
  });
});

describe("TravelScreen refine chips in scrollback", () => {
  beforeEach(() => {
    useConversation.setState({ turns: [answeredTurn, newerAnsweredTurn], busy: false });
  });

  it("shows no follow-up chips inside the conversation, only in the composer rail", async () => {
    const tree = await mount();
    expect(pressable(tree, "answer-suggestion-실내만")).toBeUndefined();
    expect(pressable(tree, "answer-suggestion-사람 적은 곳만")).toBeUndefined();
    expect(pressable(tree, "travel-chip-사람 적은 곳만")).toBeDefined();
  });

  it("refines the newest answer from the composer rail", async () => {
    const tree = await mount();
    await press(tree, "travel-chip-사람 적은 곳만");

    expect(askAgentMock).toHaveBeenCalledTimes(1);
    const input = askAgentMock.mock.calls[0][0];
    expect(input.intent).toEqual(NEWER_INTENT);
    expect(input.patch).toEqual({ crowdPreference: "quiet" });
  });
});

describe("TravelScreen chip source", () => {
  it("builds chips from refinements, not from the compatibility labels", async () => {
    useConversation.setState({ turns: [relabeledTurn], busy: false });
    const tree = await mount();

    expect(pressable(tree, "travel-chip-실내만")).toBeDefined();
    expect(pressable(tree, "travel-chip-사람 적은 곳만")).toBeUndefined();
  });

  it("falls back to starter chips when the answer carries no refinements", async () => {
    useConversation.setState({ turns: [legacyAnsweredTurn], busy: false });
    const tree = await mount();

    expect(tree.root.findAllByProps({ testID: "turn-seed-4" }).length).toBeGreaterThan(0);
    expect(pressable(tree, "travel-chip-근처 맛집")).toBeDefined();
  });
});

describe("TravelScreen zero-result turn", () => {
  const zeroTurn: Turn = {
    ...answeredTurn,
    id: "seed-zero",
    question: "제주 실내 박물관",
    request: "제주 실내 박물관",
    answer: {
      ...ANSWER,
      answer: [
        { text: "제주 + 실내 조건으로는 ", emphasis: false },
        { text: "0곳", emphasis: true },
        { text: "이에요. 조건 하나를 풀면 찾을 수 있어요.", emphasis: false },
      ],
      spots: [],
      totalCount: 0,
      refinements: [
        { label: "실내 조건 풀기", patch: { drop: "indoor" } },
        { label: "지역 넓히기", patch: { drop: "region" } },
      ],
    },
  };

  it("renders the zero answer as a normal turn, not an error", async () => {
    useConversation.setState({ turns: [zeroTurn], busy: false });
    const tree = await mount();

    expect(tree.root.findAllByProps({ testID: "turn-seed-zero" }).length).toBeGreaterThan(0);
    expect(pressable(tree, "turn-retry-seed-zero")).toBeUndefined();
  });

  it("surfaces the drop chips so the turn is not a dead end", async () => {
    useConversation.setState({ turns: [zeroTurn], busy: false });
    const tree = await mount();

    expect(pressable(tree, "travel-chip-실내 조건 풀기")).toBeDefined();
    expect(pressable(tree, "travel-chip-지역 넓히기")).toBeDefined();
  });

  it("sends the drop patch with the intent the zero turn handed back", async () => {
    useConversation.setState({ turns: [zeroTurn], busy: false });
    const tree = await mount();

    await act(async () => {
      pressable(tree, "travel-chip-실내 조건 풀기")!.props.onPress();
    });

    expect(askAgentMock).toHaveBeenCalledTimes(1);
    const input = askAgentMock.mock.calls[0][0];
    expect(input.intent).toEqual(INTENT);
    expect(input.patch).toEqual({ drop: "indoor" });
  });
});

describe("TravelScreen anchored follow-ups", () => {
  const spot = {
    contentId: "126508",
    title: "무릉계곡",
    regionLabel: "강원도 동해시",
    imageUrl: null,
    tag: "하위 8%",
    lat: 37.5,
    lng: 129.0,
  };
  const spotAnsweredTurn: Turn = {
    ...answeredTurn,
    id: "seed-6",
    answer: { ...ANSWER, spots: [spot] },
  };

  beforeEach(() => {
    useConversation.setState({ turns: [spotAnsweredTurn], busy: false });
  });

  it("anchors from its own button and swaps the composer rail to anchor chips", async () => {
    const tree = await mount();
    expect(pressable(tree, "travel-chip-근처 맛집")).toBeUndefined();

    await press(tree, "travel-spot-anchor-126508");

    expect(tree.root.findAllByProps({ testID: "travel-anchor-banner" }).length).toBeGreaterThan(0);
    expect(pressable(tree, "travel-chip-근처 맛집")).toBeDefined();
    expect(pressable(tree, "travel-chip-실내만")).toBeUndefined();
  });

  it("never anchors from a card tap", async () => {
    const tree = await mount();

    await press(tree, "travel-spot-126508");

    expect(tree.root.findAllByProps({ testID: "travel-anchor-banner" })).toHaveLength(0);
    expect(pressable(tree, "travel-chip-근처 맛집")).toBeUndefined();
  });

  it("releases the anchor when its button is pressed again", async () => {
    const tree = await mount();
    await press(tree, "travel-spot-anchor-126508");
    await press(tree, "travel-spot-anchor-126508");

    expect(tree.root.findAllByProps({ testID: "travel-anchor-banner" })).toHaveLength(0);
  });

  it("sends an anchor chip as contentId + action, labeled with the spot title", async () => {
    const tree = await mount();
    await press(tree, "travel-spot-anchor-126508");
    await press(tree, "travel-chip-근처 맛집");

    expect(askAgentMock).toHaveBeenCalledTimes(1);
    const input = askAgentMock.mock.calls[0][0];
    expect(input.anchor).toEqual({ contentId: "126508", action: "food" });
    expect(input.question).toBeFalsy();
    expect(input.intent).toBeFalsy();

    const turns = useConversation.getState().turns;
    expect(turns[turns.length - 1].question).toBe("무릉계곡 근처 맛집");
    expect(turns[turns.length - 1].anchor).toEqual({ contentId: "126508", action: "food" });
  });

  it("opens the spot detail on the first card tap", async () => {
    const { router } = jest.requireMock("expo-router") as { router: { push: jest.Mock } };
    const tree = await mount();

    await press(tree, "travel-spot-126508");

    expect(router.push).toHaveBeenCalledWith("/spots/126508");
  });

  it("still opens the detail while a card is anchored", async () => {
    const { router } = jest.requireMock("expo-router") as { router: { push: jest.Mock } };
    const tree = await mount();
    await press(tree, "travel-spot-anchor-126508");

    await press(tree, "travel-spot-126508");

    expect(router.push).toHaveBeenCalledWith("/spots/126508");
  });

  it("returns to refine chips when the anchor is cleared", async () => {
    const tree = await mount();
    await press(tree, "travel-spot-anchor-126508");
    await press(tree, "travel-anchor-clear");

    expect(pressable(tree, "travel-chip-근처 맛집")).toBeUndefined();
    expect(pressable(tree, "travel-chip-실내만")).toBeDefined();
  });

  it("drops the anchor as soon as the user types a free-text question", async () => {
    const tree = await mount();
    await press(tree, "travel-spot-anchor-126508");
    expect(pressable(tree, "travel-chip-근처 맛집")).toBeDefined();

    const input = tree.root.findByProps({ testID: "travel-input" });
    await act(async () => input.props.onChangeText("주차 가능해?"));

    expect(tree.root.findAllByProps({ testID: "travel-anchor-banner" })).toHaveLength(0);
    expect(pressable(tree, "travel-chip-근처 맛집")).toBeUndefined();
  });

  it("resends the anchor when a failed anchor turn is retried", async () => {
    useConversation.setState({
      turns: [
        spotAnsweredTurn,
        {
          ...answeredTurn,
          id: "seed-7",
          question: "무릉계곡 근처 맛집",
          request: "",
          status: "failed",
          answer: null,
          errorMessage: "실패",
          anchor: { contentId: "126508", action: "food" },
        },
      ],
      busy: false,
    });
    const tree = await mount();
    await press(tree, "turn-retry-seed-7");

    expect(askAgentMock).toHaveBeenCalledTimes(1);
    expect(askAgentMock.mock.calls[0][0].anchor).toEqual({
      contentId: "126508",
      action: "food",
    });
  });
});

describe("TravelScreen photo-first start", () => {
  it("puts a photo call to action on the empty screen", async () => {
    const tree = await mount();

    expect(tree.root.findAllByProps({ testID: "travel-start-photo" }).length).toBeGreaterThan(0);
    expect(tree.root.findByProps({ testID: "travel-greeting" }).props.pointerEvents).toBe(
      "box-none",
    );
  });

  it("takes the start actions out of reach once the conversation begins", async () => {
    useConversation.setState({ turns: [answeredTurn], busy: false });
    const tree = await mount();

    const greeting = tree.root.findByProps({ testID: "travel-greeting" });
    expect(greeting.props.pointerEvents).toBe("none");
    expect(greeting.props.importantForAccessibility).toBe("no-hide-descendants");
    expect(greeting.props.accessibilityElementsHidden).toBe(true);
  });

  it("asks for location only when the system has not decided yet", async () => {
    const askMock = jest.fn().mockResolvedValue(true);
    useNearbyCoordsMock.mockReturnValue({
      coords: null,
      phase: "unavailable",
      askable: true,
      ask: askMock,
    });
    const tree = await mount();

    await press(tree, "travel-start-location");

    expect(askMock).toHaveBeenCalled();
  });

  it("does not nag when location was already granted", async () => {
    const tree = await mount();

    expect(tree.root.findAllByProps({ testID: "travel-start-location" })).toHaveLength(0);
  });
});

describe("TravelScreen photo answer", () => {
  const photo = { uri: "file:///mine.jpg", name: "mine.jpg", type: "image/jpeg" };
  const photoTurn: Turn = {
    ...answeredTurn,
    id: "seed-photo",
    photo,
    answer: {
      ...ANSWER,
      spots: [
        {
          contentId: "126508",
          title: "월정리해변",
          regionLabel: "제주 제주시",
          imageUrl: "https://img/1.jpg",
          tag: "유사도 84%",
          lat: null,
          lng: null,
        },
      ],
    },
  };

  it("shows the uploaded photo beside the closest match", async () => {
    useConversation.setState({ turns: [photoTurn], busy: false });
    const tree = await mount();

    expect(tree.root.findAllByProps({ testID: "travel-photo-compare" }).length).toBeGreaterThan(0);
  });

  it("draws no comparison for a text-only turn", async () => {
    useConversation.setState({ turns: [answeredTurn], busy: false });
    const tree = await mount();

    expect(tree.root.findAllByProps({ testID: "travel-photo-compare" })).toHaveLength(0);
  });
});

describe("TravelScreen follow-up context", () => {
  it("carries the previous answer with a typed follow-up", async () => {
    useConversation.setState({ turns: [answeredTurn], busy: false });
    const tree = await mount();

    const input = tree.root.findByProps({ testID: "travel-input" });
    await act(async () => input.props.onChangeText("거기 근처 카페는?"));
    await press(tree, "travel-send");

    const sent = askAgentMock.mock.calls[0][0];
    expect(sent.question).toBe("거기 근처 카페는?");
    expect(sent.context.intent).toEqual(INTENT);
  });

  it("keeps the context on the turn so a retry resends it", async () => {
    useConversation.setState({ turns: [answeredTurn], busy: false });
    const tree = await mount();

    const input = tree.root.findByProps({ testID: "travel-input" });
    await act(async () => input.props.onChangeText("거기 근처 카페는?"));
    await press(tree, "travel-send");

    const turns = useConversation.getState().turns;
    expect(turns[turns.length - 1].context?.intent).toEqual(INTENT);
  });

  it("resends the context when a failed follow-up is retried", async () => {
    const failed: Turn = {
      ...answeredTurn,
      id: "seed-failed",
      question: "거기 근처 카페는?",
      request: "거기 근처 카페는?",
      status: "failed",
      answer: null,
      errorMessage: "실패",
      context: { intent: INTENT, spots: [{ contentId: "a", title: "무릉계곡" }] },
    };
    useConversation.setState({ turns: [failed], busy: false, activeId: null });
    const tree = await mount();

    await press(tree, "turn-retry-seed-failed");

    expect(askAgentMock.mock.calls[0][0].context?.spots).toEqual([
      { contentId: "a", title: "무릉계곡" },
    ]);
  });

  it("sends no context on the very first question", async () => {
    const tree = await mount();

    const input = tree.root.findByProps({ testID: "travel-input" });
    await act(async () => input.props.onChangeText("제주 계곡"));
    await press(tree, "travel-send");

    expect(askAgentMock.mock.calls[0][0].context).toBeNull();
  });
});

describe("TravelScreen map", () => {
  const pinned = [
    {
      contentId: "126508",
      title: "무릉계곡",
      regionLabel: "제주 제주시",
      imageUrl: null,
      tag: null,
      lat: 33.5,
      lng: 126.5,
    },
    {
      contentId: "126509",
      title: "천지연",
      regionLabel: "제주 서귀포시",
      imageUrl: null,
      tag: null,
      lat: 33.25,
      lng: 126.56,
    },
  ];
  const mapTurn: Turn = {
    ...answeredTurn,
    id: "seed-map",
    question: "제주에서 한적한 곳",
    answer: { ...ANSWER, spots: pinned },
  };

  const openMap = async (tree: Awaited<ReturnType<typeof mount>>) => {
    await act(async () => {
      tree.root.findByProps({ testID: "travel-turn-map" }).props.onPress();
    });
  };

  it("keeps the map sheet closed until the turn map is tapped", async () => {
    useConversation.setState({ turns: [mapTurn], busy: false });
    const tree = await mount();

    expect(tree.root.findAllByProps({ testID: "travel-map-sheet" })).toHaveLength(0);
  });

  it("opens the sheet with a card per pinned result", async () => {
    useConversation.setState({ turns: [mapTurn], busy: false });
    const tree = await mount();

    await openMap(tree);

    expect(tree.root.findAllByProps({ testID: "travel-map-sheet" }).length).toBeGreaterThan(0);
    expect(tree.root.findAllByProps({ testID: "travel-map-card-126508" }).length).toBeGreaterThan(
      0,
    );
    expect(tree.root.findAllByProps({ testID: "travel-map-card-126509" }).length).toBeGreaterThan(
      0,
    );
  });

  it("closes the sheet from its own button", async () => {
    useConversation.setState({ turns: [mapTurn], busy: false });
    const tree = await mount();
    await openMap(tree);

    await press(tree, "travel-map-close");

    expect(tree.root.findAllByProps({ testID: "travel-map-sheet" })).toHaveLength(0);
  });

  it("offers no map when the answer carries no coordinates", async () => {
    useConversation.setState({ turns: [answeredTurn], busy: false });
    const tree = await mount();

    expect(tree.root.findAllByProps({ testID: "travel-turn-map" })).toHaveLength(0);
  });
});

describe("TravelScreen retry", () => {
  it("resends intent and patch when a failed refine turn is retried", async () => {
    useConversation.setState({ turns: [answeredTurn, failedRefineTurn], busy: false });
    const tree = await mount();
    await press(tree, "turn-retry-seed-3");

    expect(askAgentMock).toHaveBeenCalledTimes(1);
    const input = askAgentMock.mock.calls[0][0];
    expect(input.intent).toEqual(INTENT);
    expect(input.patch).toEqual({ indoorOnly: true });
    expect(input.question).toBeFalsy();
    expect(useConversation.getState().turns).toHaveLength(2);
  });

  it("resends the original text when a failed plain question turn is retried", async () => {
    useConversation.setState({
      turns: [{ ...answeredTurn, status: "failed", answer: null, errorMessage: "실패" }],
      busy: false,
    });
    const tree = await mount();
    await press(tree, "turn-retry-seed-1");

    expect(askAgentMock).toHaveBeenCalledTimes(1);
    const input = askAgentMock.mock.calls[0][0];
    expect(input.question).toBe("여름에 시원한 계곡");
    expect(input.intent).toBeFalsy();
    expect(input.patch).toBeFalsy();
  });
});
