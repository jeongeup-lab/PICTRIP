import renderer, { act } from "react-test-renderer";
import { FlatList, Keyboard, ScrollView, StyleSheet } from "react-native";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import TravelScreen, {
  ASK_PLACEHOLDER,
  ATTACHED_PLACEHOLDER,
  LOCATION_CHECKING,
  LOCATION_REQUIRED,
} from "@/app/(tabs)/travel";
import {
  askAgent,
  type AgentAnswer,
  type QueryIntent,
  type TravelSpot,
} from "@/features/travel/api";
import { useNearbyCoords } from "@/features/travel/hooks/use-nearby-coords";
import { useConversation, type Turn } from "@/features/travel/stores/conversation-store";
import { useTravelAnchor } from "@/features/travel/stores/anchor-store";
import { KakaoWebMap } from "@/features/map/components/KakaoWebMap";
import { AnswerBar, FAIL_TITLE } from "@/features/travel/components/AnswerBar";
import { SpotCarousel, CAROUSEL_BLOCK_PX } from "@/features/travel/components/SpotCarousel";
import { SearchPulse } from "@/features/travel/components/SearchPulse";
import { CARD_STRIDE } from "@/features/travel/components/SpotCard";
import { PHOTO_PICK_FAILED, PHOTO_SHOOT_FAILED } from "@/features/travel/lib/agent-errors";
import {
  ATTACH_HEADLINE,
  ATTACH_NOTICE,
  TravelDock,
} from "@/features/travel/components/TravelDock";
import { PHOTO_CHIP_LABEL, PHOTO_CHIP_TEST_ID } from "@/features/travel/components/ChipRow";
import { dockBasePx, panelBasePx } from "@/features/travel/lib/screen-layout";

jest.mock("expo-router", () => ({ router: { push: jest.fn(), back: jest.fn() } }));
jest.mock("react-native-safe-area-context", () => ({
  SafeAreaView: (props: { children?: unknown }) => props.children,
  useSafeAreaInsets: () => ({ top: 44, bottom: 34, left: 0, right: 0 }),
}));
jest.mock("@/features/travel/hooks/use-nearby-coords", () => ({ useNearbyCoords: jest.fn() }));
jest.mock("@/features/travel/usecases/pick-travel-photo", () => ({
  pickTravelPhoto: jest.fn(async () => null),
  shootTravelPhoto: jest.fn(async () => null),
}));
jest.mock("@/features/travel/api", () => ({ askAgent: jest.fn() }));
jest.mock("@/features/saved/hooks/use-save-optimistic", () => ({
  useSaveOptimistic: jest.fn(),
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
const { useSaveOptimistic } = jest.requireMock("@/features/saved/hooks/use-save-optimistic") as {
  useSaveOptimistic: jest.Mock;
};
const toggleSave = jest.fn();

const COORDS = { lat: 37.5665, lng: 126.978 };
const PHOTO = { uri: "file:///a.jpg", name: "a.jpg", type: "image/jpeg" };

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

const PINNED: TravelSpot[] = [
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
  {
    contentId: "126510",
    title: "쇠소깍",
    regionLabel: "제주 서귀포시",
    imageUrl: null,
    tag: null,
    lat: 33.28,
    lng: 126.6,
  },
];

const SEED: TravelSpot = {
  contentId: "126511",
  title: "성산일출봉",
  regionLabel: "제주 서귀포시",
  imageUrl: null,
  tag: null,
  lat: 33.46,
  lng: 126.94,
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

const legacyAnsweredTurn: Turn = {
  ...answeredTurn,
  id: "seed-4",
  answer: { ...ANSWER, suggestions: ["실내만"], refinements: undefined },
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

const photoAnsweredTurn: Turn = {
  ...answeredTurn,
  id: "seed-photo",
  question: "이 사진 같은 분위기의 여행지",
  request: "",
  photo: PHOTO,
};

const mapTurn: Turn = {
  ...answeredTurn,
  id: "seed-map",
  question: "제주에서 한적한 곳",
  answer: { ...ANSWER, spots: PINNED },
};

let mounted: renderer.ReactTestRenderer | null = null;
let client: QueryClient;

const CLEAR_TURNS = useConversation.getState().clear;

beforeEach(() => {
  jest.clearAllMocks();
  useConversation.setState({ clear: CLEAR_TURNS });
  useConversation.getState().clear();
  useTravelAnchor.getState().clear();
  useNearbyCoordsMock.mockReturnValue({
    coords: COORDS,
    phase: "ready",
    askable: false,
    ask: jest.fn(),
  });
  toggleSave.mockResolvedValue(true);
  useSaveOptimistic.mockReturnValue({ saved: false, toggle: toggleSave });
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
  jest.restoreAllMocks();
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

async function press(tree: renderer.ReactTestRenderer, testID: string) {
  const node = pressable(tree, testID);
  if (!node) throw new Error(`no pressable with testID ${testID}`);
  await act(async () => node.props.onPress());
}

function chip(tree: renderer.ReactTestRenderer, label: string) {
  return tree.root
    .findAll(
      (node) =>
        typeof node.props.testID === "string" &&
        node.props.testID.startsWith("travel-chip-") &&
        typeof node.props.onPress === "function",
    )
    .find((node) => node.props.accessibilityLabel === label);
}

async function pressChip(tree: renderer.ReactTestRenderer, label: string) {
  const node = chip(tree, label);
  if (!node) throw new Error(`no chip labeled ${label}`);
  await act(async () => node.props.onPress());
}

async function type(tree: renderer.ReactTestRenderer, text: string) {
  const input = tree.root.findByProps({ testID: "travel-input" });
  await act(async () => input.props.onChangeText(text));
}

function placeholder(tree: renderer.ReactTestRenderer) {
  return tree.root.findByProps({ testID: "travel-input" }).props.placeholder;
}

function carousel(tree: renderer.ReactTestRenderer) {
  return tree.root.findByType(SpotCarousel);
}

function panelShown(tree: renderer.ReactTestRenderer): boolean {
  return tree.root.findAllByProps({ testID: "travel-result-panel" }).length > 0;
}

function answerBar(tree: renderer.ReactTestRenderer) {
  return tree.root.findByType(AnswerBar);
}

function mapView(tree: renderer.ReactTestRenderer) {
  return tree.root.findByType(KakaoWebMap);
}

function panelBottom(tree: renderer.ReactTestRenderer): number {
  const panel = tree.root.findAllByProps({ testID: "travel-result-panel" })[0];
  return StyleSheet.flatten(panel.props.style).bottom as number;
}

async function layoutPanel(tree: renderer.ReactTestRenderer, height: number) {
  const panel = tree.root.findAllByProps({ testID: "travel-result-panel" })[0];
  await act(async () => panel.props.onLayout({ nativeEvent: { layout: { height } } }));
}

function toastBottom(tree: renderer.ReactTestRenderer): number {
  return tree.root.findByProps({ testID: "travel-toast" }).props.bottom as number;
}

function dockBottom(tree: renderer.ReactTestRenderer): number {
  return tree.root.findByType(TravelDock).props.bottom;
}

function rendered(tree: renderer.ReactTestRenderer) {
  return JSON.stringify(tree.toJSON());
}

async function swipeTo(tree: renderer.ReactTestRenderer, index: number) {
  const list = tree.root.findByType(FlatList);
  await act(async () =>
    list.props.onMomentumScrollEnd({ nativeEvent: { contentOffset: { x: CARD_STRIDE * index } } }),
  );
}

async function seed(spot: TravelSpot) {
  await act(async () => useTravelAnchor.setState({ spot }));
}

async function pressSave(tree: renderer.ReactTestRenderer, contentId: string) {
  await press(tree, `travel-card-save-${contentId}`);
}

describe("TravelScreen starter chips", () => {
  it("좌표가 있으면 근처 칩이 스팟 없는 앵커로 나간다", async () => {
    const tree = await mount();
    await pressChip(tree, "근처 맛집");

    expect(askAgentMock).toHaveBeenCalledTimes(1);
    const input = askAgentMock.mock.calls[0][0];
    expect(input.anchor).toEqual({ action: "food" });
    expect(input.coords).toEqual(COORDS);
    expect(input.question).toBeUndefined();
    expect(input.intent).toBeUndefined();
  });

  it("근처 볼거리는 앵커가 아니라 intent 로 나간다 — 3km 반경에 갇히지 않는다", async () => {
    const tree = await mount();
    await pressChip(tree, "근처 볼거리");

    const input = askAgentMock.mock.calls[0][0];
    expect(input.intent?.nearMe).toBe(true);
    expect(input.anchor).toBeUndefined();
  });

  it("좌표가 없어도 칩 줄은 그대로다 — 누르면 그때 위치를 묻는다", async () => {
    const askMock = jest.fn().mockResolvedValue(true);
    useNearbyCoordsMock.mockReturnValue({
      coords: null,
      phase: "unavailable",
      askable: true,
      ask: askMock,
    });
    const tree = await mount();

    expect(chip(tree, "근처 맛집")).toBeDefined();
    await pressChip(tree, "근처 맛집");

    expect(askMock).toHaveBeenCalled();
    expect(askAgentMock).not.toHaveBeenCalled();
  });

  it("첫 화면 칩은 사진 뒤에 근처 세 갈래로 고정이다", async () => {
    const tree = await mount();
    const labels = ["근처 카페", "근처 맛집", "근처 볼거리"];

    for (const label of labels) expect(chip(tree, label)).toBeDefined();
    expect(chip(tree, "지금 축제")).toBeUndefined();
    expect(chip(tree, "사람 적은 바닷가")).toBeUndefined();
  });

  it("첫 화면 칩 줄은 고정된 사진 칩으로 시작한다", async () => {
    const tree = await mount();
    const labels = tree.root
      .findAll(
        (node) =>
          typeof node.props.testID === "string" &&
          node.props.testID.startsWith("travel-chip-") &&
          typeof node.props.onPress === "function" &&
          typeof node.props.accessibilityLabel === "string",
      )
      .map((node) => node.props.accessibilityLabel);

    const tracks = tree.root.findAllByType(ScrollView);

    expect(labels[0]).toBe(PHOTO_CHIP_LABEL);
    expect(pressable(tree, PHOTO_CHIP_TEST_ID)).toBeDefined();
    expect(tracks.length).toBeGreaterThan(0);
    expect(tracks.flatMap((track) => track.findAllByProps({ testID: PHOTO_CHIP_TEST_ID }))).toEqual(
      [],
    );
  });
});

describe("TravelScreen nearby action", () => {
  it("포커스한 카드가 없으면 근처 칩은 내 위치를 뜻한다", async () => {
    const tree = await mount();
    await pressChip(tree, "근처 카페");

    expect(askAgentMock.mock.calls[0][0].anchor).toEqual({ action: "cafe" });
    const turns = useConversation.getState().turns;
    expect(turns[turns.length - 1].question).toBe("내 위치 근처 카페");
  });

  it("위치를 영영 못 쓰면 근처 칩은 토스트로 이유를 말한다", async () => {
    useNearbyCoordsMock.mockReturnValue({
      coords: null,
      phase: "unavailable",
      askable: false,
      ask: jest.fn(),
    });
    const tree = await mount();

    await pressChip(tree, "근처 카페");

    expect(askAgentMock).not.toHaveBeenCalled();
    expect(rendered(tree)).toContain(LOCATION_REQUIRED);
  });

  it("좌표를 아직 확인하는 중이면 거절한 것처럼 말하지 않는다", async () => {
    const askMock = jest.fn();
    useNearbyCoordsMock.mockReturnValue({
      coords: null,
      phase: "checking",
      askable: false,
      ask: askMock,
    });
    const tree = await mount();

    await pressChip(tree, "근처 카페");

    expect(askAgentMock).not.toHaveBeenCalled();
    expect(askMock).not.toHaveBeenCalled();
    expect(rendered(tree)).toContain(LOCATION_CHECKING);
    expect(rendered(tree)).not.toContain(LOCATION_REQUIRED);
  });

  it("위치를 아직 정하지 않았으면 켜기를 권한다", async () => {
    const askMock = jest.fn().mockResolvedValue(true);
    useNearbyCoordsMock.mockReturnValue({
      coords: null,
      phase: "unavailable",
      askable: true,
      ask: askMock,
    });
    const tree = await mount();

    await press(tree, "travel-ask-location");

    expect(askMock).toHaveBeenCalled();
  });

  it("이미 허용된 위치는 다시 조르지 않는다", async () => {
    const tree = await mount();

    expect(tree.root.findAllByProps({ testID: "travel-ask-location" })).toHaveLength(0);
  });
});

describe("TravelScreen photo attach", () => {
  it("carries the text already typed in the dock along with the photo", async () => {
    pickTravelPhoto.mockResolvedValueOnce(PHOTO);
    const tree = await mount();
    await type(tree, "제주 바다 같은 곳");

    await pressChip(tree, PHOTO_CHIP_LABEL);
    await press(tree, "travel-send");

    expect(askAgentMock).toHaveBeenCalledTimes(1);
    const sent = askAgentMock.mock.calls[0][0];
    expect(sent.question).toBe("제주 바다 같은 곳");
    expect(sent.photo).toEqual(PHOTO);
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

  it("카메라를 열지 못하면 입력을 유지하고 오류 토스트를 보여준다", async () => {
    shootTravelPhoto.mockRejectedValueOnce(new Error("denied"));
    const tree = await mount();
    await type(tree, "제주 바다 같은 곳");

    await press(tree, "travel-shoot");

    expect(askAgentMock).not.toHaveBeenCalled();
    expect(tree.root.findByProps({ testID: "travel-input" }).props.value).toBe("제주 바다 같은 곳");
    expect(rendered(tree)).toContain(PHOTO_SHOOT_FAILED);
  });

  it("only attaches a selected photo until the user sends it", async () => {
    pickTravelPhoto.mockResolvedValueOnce(PHOTO);
    const tree = await mount();
    await pressChip(tree, PHOTO_CHIP_LABEL);

    expect(askAgentMock).not.toHaveBeenCalled();
    expect(tree.root.findAllByProps({ testID: "travel-attach-banner" }).length).toBeGreaterThan(0);

    await press(tree, "travel-send");
    expect(askAgentMock).toHaveBeenCalledTimes(1);
    expect(askAgentMock.mock.calls[0][0].question).toBe("");
    expect(askAgentMock.mock.calls[0][0].photo).toEqual(PHOTO);
  });

  it("tells the user what sending the photo will do instead of restating the attachment", async () => {
    pickTravelPhoto.mockResolvedValueOnce(PHOTO);
    const tree = await mount();

    expect(placeholder(tree)).toBe(ASK_PLACEHOLDER);

    await pressChip(tree, PHOTO_CHIP_LABEL);

    const dock = rendered(tree);
    expect(dock).toContain(ATTACH_HEADLINE);
    expect(dock).toContain(ATTACH_NOTICE);
    expect(dock).not.toContain("폐기");
    expect(placeholder(tree)).toBe(ATTACHED_PLACEHOLDER);
  });

  it("does not spell out a sample question in the placeholder", () => {
    expect(ASK_PLACEHOLDER).not.toContain("예:");
    expect(ASK_PLACEHOLDER).not.toContain("부산");
  });

  it("keeps the draft and shows the shared toast when picking rejects", async () => {
    pickTravelPhoto.mockRejectedValueOnce(new Error("picker failed"));
    const tree = await mount();
    await type(tree, "제주 바다 같은 곳");

    await pressChip(tree, PHOTO_CHIP_LABEL);

    expect(askAgentMock).not.toHaveBeenCalled();
    expect(tree.root.findByProps({ testID: "travel-input" }).props.value).toBe("제주 바다 같은 곳");
    expect(rendered(tree)).toContain(PHOTO_PICK_FAILED);
  });

  it("첨부를 지우면 칩 줄이 돌아온다", async () => {
    pickTravelPhoto.mockResolvedValueOnce(PHOTO);
    const tree = await mount();
    await pressChip(tree, PHOTO_CHIP_LABEL);

    await press(tree, "travel-attach-clear");

    expect(tree.root.findAllByProps({ testID: "travel-attach-banner" })).toHaveLength(0);
    expect(chip(tree, PHOTO_CHIP_LABEL)).toBeDefined();
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
    expect(tree.root.findAllByType(AnswerBar)).toHaveLength(0);
    expect(chip(tree, "근처 맛집")).toBeDefined();
  });

  it("새 대화는 캐러셀 포커스도 첫 칸으로 되돌린다", async () => {
    useConversation.setState({ turns: [mapTurn], busy: false });
    const tree = await mount();
    await swipeTo(tree, 2);
    expect(carousel(tree).props.focusedIndex).toBe(2);

    await press(tree, "travel-new-chat");

    expect(panelShown(tree)).toBe(false);
  });

  it("새 대화 뒤 다시 물으면 캐러셀이 첫 칸에서 시작한다", async () => {
    useConversation.setState({ turns: [mapTurn], busy: false });
    const tree = await mount();
    await swipeTo(tree, 2);
    await press(tree, "travel-new-chat");

    await act(async () => useConversation.setState({ turns: [mapTurn], busy: false }));

    expect(carousel(tree).props.focusedIndex).toBe(0);
    expect(carousel(tree).props.scrollToIndex).toBeNull();
  });
});

describe("TravelScreen answer bar", () => {
  const longTurn: Turn = {
    ...answeredTurn,
    id: "seed-long",
    answer: {
      ...ANSWER,
      answer: [
        { text: "제주 계곡 3곳을 추렸어요. ", emphasis: false },
        { text: "주말엔 붐빌 수 있어요.", emphasis: false },
      ],
      spots: PINNED,
    },
  };

  it("headline 은 첫 문장만 보여준다", async () => {
    useConversation.setState({ turns: [longTurn], busy: false });
    const tree = await mount();

    expect(rendered(tree)).toContain("제주 계곡 3곳을 추렸어요.");
    expect(rendered(tree)).not.toContain("주말엔 붐빌 수 있어요.");
  });

  it("펼치면 나머지 문장이 따라 나온다", async () => {
    useConversation.setState({ turns: [longTurn], busy: false });
    const tree = await mount();

    await press(tree, "travel-answer-toggle");

    expect(answerBar(tree).props.expanded).toBe(true);
    expect(rendered(tree)).toContain("주말엔 붐빌 수 있어요.");
  });

  it("결과가 없는 답은 접을 것도 없이 처음부터 펼쳐 둔다", async () => {
    useConversation.setState({ turns: [answeredTurn], busy: false });
    const tree = await mount();

    expect(answerBar(tree).props.expanded).toBe(true);
  });

  it("결과가 없는 답은 접을 수 없다고 알려 토글을 지운다", async () => {
    useConversation.setState({ turns: [answeredTurn], busy: false });
    const tree = await mount();

    expect(answerBar(tree).props.collapsible).toBe(false);
    expect(pressable(tree, "travel-answer-toggle")).toBeUndefined();
    expect(tree.root.findAllByProps({ accessibilityLabel: "답변 접기" })).toHaveLength(0);
  });

  it("결과가 있는 답에는 접는 토글이 남는다", async () => {
    useConversation.setState({ turns: [longTurn], busy: false });
    const tree = await mount();

    expect(answerBar(tree).props.collapsible).toBe(true);
    expect(pressable(tree, "travel-answer-toggle")).toBeDefined();
  });

  it("답이 오기 전에는 진행 단계를 걸고 오류는 비워 둔다", async () => {
    useConversation.setState({
      turns: [{ ...answeredTurn, status: "pending", answer: null }],
      busy: true,
      activeId: "seed-1",
    });
    const tree = await mount();

    expect(answerBar(tree).props.step).toBe("질문에서 조건 읽는 중");
    expect(answerBar(tree).props.errorMessage).toBeNull();
  });

  it("대화가 없으면 답변 바 자체가 없다", async () => {
    const tree = await mount();

    expect(tree.root.findAllByType(AnswerBar)).toHaveLength(0);
  });
});

describe("TravelScreen carousel focus", () => {
  beforeEach(() => {
    useConversation.setState({ turns: [mapTurn], busy: false });
  });

  it("첫 카드가 곧바로 문맥이 된다", async () => {
    const tree = await mount();

    expect(carousel(tree).props.focusedIndex).toBe(0);
    expect(chip(tree, "무릉계곡 근처 카페")).toBeDefined();
    expect(placeholder(tree)).toBe("무릉계곡에 대해 물어보기");
  });

  it("스와이프하면 문맥 칩과 플레이스홀더가 따라 바뀐다", async () => {
    const tree = await mount();

    await swipeTo(tree, 1);

    expect(chip(tree, "천지연 근처 카페")).toBeDefined();
    expect(chip(tree, "무릉계곡 근처 카페")).toBeUndefined();
    expect(placeholder(tree)).toBe("천지연에 대해 물어보기");
  });

  it("문맥 칩은 세 갈래 모두 카드 이름을 앞에 단다", async () => {
    const tree = await mount();
    await swipeTo(tree, 1);

    for (const label of ["천지연 근처 카페", "천지연 근처 맛집", "천지연 근처 볼거리"]) {
      expect(chip(tree, label)).toBeDefined();
    }
  });

  it("문맥 칩은 포커스한 카드의 contentId 로 나가고 칩 글씨가 곧 질문이다", async () => {
    const tree = await mount();
    await swipeTo(tree, 1);

    await pressChip(tree, "천지연 근처 맛집");

    expect(askAgentMock.mock.calls[0][0].anchor).toEqual({
      contentId: "126509",
      action: "food",
    });
    const turns = useConversation.getState().turns;
    expect(turns[turns.length - 1].question).toBe("천지연 근처 맛집");
  });

  it("포커스한 카드는 지도에서도 같은 카드를 가리킨다", async () => {
    const tree = await mount();

    await swipeTo(tree, 2);

    expect(mapView(tree).props.anchorId).toBe("126510");
  });

  it("스와이프하면 지도가 그 카드로 팬한다", async () => {
    const tree = await mount();

    expect(mapView(tree).props.center).toEqual({ lat: 33.5, lng: 126.5 });

    await swipeTo(tree, 2);

    expect(mapView(tree).props.center).toEqual({ lat: 33.28, lng: 126.6 });
  });

  it("핀 탭으로 옮긴 포커스도 지도를 그리로 팬한다", async () => {
    jest.spyOn(FlatList.prototype, "scrollToOffset").mockImplementation(() => {});
    const tree = await mount();

    await act(async () => mapView(tree).props.onPinTap("126509"));

    expect(mapView(tree).props.center).toEqual({ lat: 33.25, lng: 126.56 });
  });
});

describe("TravelScreen dock height", () => {
  beforeEach(() => {
    useConversation.setState({ turns: [mapTurn], busy: false });
  });

  it("독은 씬 바닥에 붙고 탭 바 높이만큼 들리지 않는다", async () => {
    const tree = await mount();

    expect(dockBottom(tree)).toBe(0);
  });

  it("캐러셀 자리는 독 높이만큼만 위에 앉는다", async () => {
    const tree = await mount();

    expect(panelBottom(tree)).toBe(dockBasePx({ primer: false, attached: false, chips: false }));
  });

  it("위치 프라이머가 뜨면 캐러셀을 그만큼 위로 올린다", async () => {
    const settled = await mount();
    const low = panelBottom(settled);
    await act(async () => settled.unmount());
    mounted = null;

    useNearbyCoordsMock.mockReturnValue({
      coords: COORDS,
      phase: "ready",
      askable: true,
      ask: jest.fn(),
    });
    const tree = await mount();

    expect(panelBottom(tree)).toBeGreaterThan(low);
    expect(panelBottom(tree) - low).toBe(47);
  });

  it("사진을 첨부하면 두꺼워진 배너만큼 캐러셀을 올린다", async () => {
    pickTravelPhoto.mockResolvedValueOnce(PHOTO);
    const tree = await mount();
    const low = panelBottom(tree);

    await pressChip(tree, PHOTO_CHIP_LABEL);

    expect(panelBottom(tree) - low).toBe(73);
  });

  it("첨부 중에는 프라이머가 사라지므로 두 번 더하지 않는다", async () => {
    useNearbyCoordsMock.mockReturnValue({
      coords: COORDS,
      phase: "ready",
      askable: true,
      ask: jest.fn(),
    });
    pickTravelPhoto.mockResolvedValueOnce(PHOTO);
    const tree = await mount();
    const withPrimer = panelBottom(tree);

    await pressChip(tree, PHOTO_CHIP_LABEL);

    expect(panelBottom(tree)).toBe(withPrimer - 47 + 73);
  });

  it("펼쳐서 자란 패널 높이가 지도 여백과 토스트에 반영된다", async () => {
    const tree = await mount();
    const dock = dockBasePx({ primer: false, attached: false, chips: false });
    await layoutPanel(tree, 500);

    expect(mapView(tree).props.fit.pad.bottom).toBe(dock + 500 + 24);
    expect(toastBottom(tree)).toBe(dock + 500 + 12);
  });

  it("실측이 오기 전에는 어림값으로 버틴다", async () => {
    const tree = await mount();

    expect(mapView(tree).props.fit.pad.bottom).toBe(
      dockBasePx({ primer: false, attached: false, chips: false }) +
        panelBasePx({ chips: true, carousel: true }) +
        CAROUSEL_BLOCK_PX +
        24,
    );
  });

  it("독이 자란 만큼 지도 여백과 토스트도 함께 밀린다", async () => {
    const settled = await mount();
    const low = settled.root.findByType(KakaoWebMap).props.fit.pad.bottom;
    await act(async () => settled.unmount());
    mounted = null;

    useNearbyCoordsMock.mockReturnValue({
      coords: COORDS,
      phase: "ready",
      askable: true,
      ask: jest.fn(),
    });
    const tree = await mount();

    expect(mapView(tree).props.fit.pad.bottom - low).toBe(47);
  });
});

describe("TravelScreen 질의 중 스켈레톤", () => {
  const pendingTurn: Turn = {
    ...answeredTurn,
    id: "seed-pending",
    status: "pending",
    answer: null,
  };

  function skeleton(tree: renderer.ReactTestRenderer) {
    return tree.root.findAllByProps({ testID: "travel-carousel-skeleton" });
  }

  function pulseBottom(tree: renderer.ReactTestRenderer): number {
    return tree.root.findByType(SearchPulse).props.bottom as number;
  }

  it("답을 기다리는 동안 캐러셀 자리를 스켈레톤으로 채운다", async () => {
    useConversation.setState({ turns: [pendingTurn], busy: true, activeId: "seed-pending" });
    const tree = await mount();

    expect(skeleton(tree).length).toBeGreaterThan(0);
    expect(carousel(tree).props.spots).toEqual([]);
    expect(tree.root.findAllByProps({ testID: "travel-carousel" })).toHaveLength(0);
  });

  it("스켈레톤은 포커스를 알리지 않는다", async () => {
    useConversation.setState({ turns: [pendingTurn], busy: true, activeId: "seed-pending" });
    const tree = await mount();

    expect(tree.root.findAllByType(FlatList)).toHaveLength(0);
    expect(carousel(tree).props.focusedIndex).toBe(0);
  });

  it("질의 중과 결과 사이에서 독 높이가 그대로다", async () => {
    useConversation.setState({ turns: [pendingTurn], busy: true, activeId: "seed-pending" });
    const waiting = await mount();
    const whileWaiting = pulseBottom(waiting);
    await act(async () => waiting.unmount());
    mounted = null;

    useConversation.setState({ turns: [mapTurn], busy: false, activeId: null });
    const answered = await mount();

    expect(pulseBottom(answered)).toBe(whileWaiting);
  });

  it("빈 상태는 캐러셀 자체가 없고 씨앗 상태는 스켈레톤 없이 카드만 그린다", async () => {
    const empty = await mount();
    expect(skeleton(empty)).toHaveLength(0);
    expect(empty.root.findAllByProps({ testID: "travel-carousel" })).toHaveLength(0);
    await act(async () => empty.unmount());
    mounted = null;

    useTravelAnchor.setState({ spot: SEED });
    const seeded = await mount();

    expect(skeleton(seeded)).toHaveLength(0);
    expect(seeded.root.findAllByProps({ testID: "travel-carousel" }).length).toBeGreaterThan(0);
  });
});

describe("TravelScreen 질의 중 칩 잠금", () => {
  const busyTurn: Turn = {
    ...answeredTurn,
    id: "seed-busy",
    status: "pending",
    answer: null,
  };

  beforeEach(() => {
    useConversation.setState({ turns: [busyTurn], busy: true, activeId: "seed-busy" });
  });

  it("응답을 기다리는 동안 사진 칩은 앨범을 열지 않는다", async () => {
    pickTravelPhoto.mockResolvedValueOnce(PHOTO);
    const tree = await mount();

    await pressChip(tree, PHOTO_CHIP_LABEL);

    expect(pickTravelPhoto).not.toHaveBeenCalled();
    expect(tree.root.findAllByProps({ testID: "travel-attach-banner" })).toHaveLength(0);
    expect(placeholder(tree)).toBe(ASK_PLACEHOLDER);
  });

  it("응답을 기다리는 동안 문맥 칩도 새 질문을 내지 않는다", async () => {
    useConversation.setState({
      turns: [{ ...mapTurn, status: "pending", answer: null }],
      busy: true,
      activeId: "seed-map",
    });
    const tree = await mount();

    await pressChip(tree, PHOTO_CHIP_LABEL);

    expect(askAgentMock).not.toHaveBeenCalled();
    expect(useConversation.getState().turns).toHaveLength(1);
  });

  it("응답을 기다리는 동안 칩은 누를 수 없는 상태로 그려진다", async () => {
    const tree = await mount();

    expect(chip(tree, PHOTO_CHIP_LABEL)!.props.disabled).toBe(true);
  });
});

describe("TravelScreen pin tap", () => {
  beforeEach(() => {
    useConversation.setState({ turns: [mapTurn], busy: false });
  });

  it("핀을 누르면 캐러셀을 그 카드로 스크롤한다", async () => {
    const scrollToOffset = jest
      .spyOn(FlatList.prototype, "scrollToOffset")
      .mockImplementation(() => {});
    const tree = await mount();

    await act(async () => mapView(tree).props.onPinTap("126509"));

    expect(scrollToOffset).toHaveBeenCalledWith({ offset: CARD_STRIDE, animated: true });
  });

  it("포커스와 스크롤 지시가 같은 값으로 함께 간다", async () => {
    jest.spyOn(FlatList.prototype, "scrollToOffset").mockImplementation(() => {});
    const tree = await mount();

    await act(async () => mapView(tree).props.onPinTap("126510"));

    expect(carousel(tree).props.focusedIndex).toBe(2);
    expect(carousel(tree).props.scrollToIndex).toBe(2);
  });

  it("핀 탭으로 옮긴 문맥이 칩 줄에도 반영된다", async () => {
    jest.spyOn(FlatList.prototype, "scrollToOffset").mockImplementation(() => {});
    const tree = await mount();

    await act(async () => mapView(tree).props.onPinTap("126509"));

    expect(chip(tree, "천지연 근처 카페")).toBeDefined();
  });

  it("지도에 없는 스팟의 핀 탭은 무시한다", async () => {
    const tree = await mount();

    await act(async () => mapView(tree).props.onPinTap("999999"));

    expect(carousel(tree).props.focusedIndex).toBe(0);
    expect(carousel(tree).props.scrollToIndex).toBeNull();
  });
});

describe("TravelScreen refine chips", () => {
  beforeEach(() => {
    useConversation.setState({ turns: [answeredTurn], busy: false });
  });

  it("sends the refine chip as intent + patch, not as text", async () => {
    const tree = await mount();
    await pressChip(tree, "실내만");

    expect(askAgentMock).toHaveBeenCalledTimes(1);
    const input = askAgentMock.mock.calls[0][0];
    expect(input.patch).toEqual({ indoorOnly: true });
    expect(input.intent).toEqual(INTENT);
    expect(input.question).toBeFalsy();
  });

  it("labels the new turn with the chip so the answer bar can name it", async () => {
    const tree = await mount();
    await pressChip(tree, "실내만");

    const turns = useConversation.getState().turns;
    expect(turns).toHaveLength(2);
    expect(turns[1].question).toBe("실내만");
    expect(turns[1].intent).toEqual(INTENT);
    expect(turns[1].patch).toEqual({ indoorOnly: true });
  });

  it("keeps the source photo while sending intent and patch without a question", async () => {
    useConversation.setState({ turns: [photoAnsweredTurn], busy: false });
    const tree = await mount();
    await pressChip(tree, "실내만");

    const input = askAgentMock.mock.calls[0][0];
    expect(input.photo).toEqual(PHOTO);
    expect(input.intent).toEqual(INTENT);
    expect(input.patch).toEqual({ indoorOnly: true });
    expect(input.question).toBeFalsy();
  });
});

describe("TravelScreen chip source", () => {
  it("builds chips from refinements, not from the compatibility labels", async () => {
    useConversation.setState({ turns: [relabeledTurn], busy: false });
    const tree = await mount();

    expect(chip(tree, "실내만")).toBeDefined();
    expect(chip(tree, "사람 적은 곳만")).toBeUndefined();
  });

  it("keeps starter chips out once an answer landed, even without refinements", async () => {
    useConversation.setState({ turns: [legacyAnsweredTurn], busy: false });
    const tree = await mount();

    expect(chip(tree, PHOTO_CHIP_LABEL)).toBeDefined();
    expect(chip(tree, "근처 맛집")).toBeUndefined();
    expect(chip(tree, "근처 카페")).toBeUndefined();
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

  beforeEach(() => {
    useConversation.setState({ turns: [zeroTurn], busy: false });
  });

  it("renders the zero answer as a normal answer, not an error", async () => {
    const tree = await mount();

    expect(answerBar(tree).props.errorMessage).toBeNull();
    expect(rendered(tree)).not.toContain(FAIL_TITLE);
    expect(pressable(tree, "travel-retry")).toBeUndefined();
  });

  it("surfaces the drop chips so the turn is not a dead end", async () => {
    const tree = await mount();

    expect(chip(tree, "실내 조건 풀기")).toBeDefined();
    expect(chip(tree, "지역 넓히기")).toBeDefined();
  });

  it("sends the drop patch with the intent the zero turn handed back", async () => {
    const tree = await mount();

    await pressChip(tree, "실내 조건 풀기");

    expect(askAgentMock).toHaveBeenCalledTimes(1);
    const input = askAgentMock.mock.calls[0][0];
    expect(input.intent).toEqual(INTENT);
    expect(input.patch).toEqual({ drop: "indoor" });
  });

  it("결과가 없으면 캐러셀도 그리지 않는다", async () => {
    const tree = await mount();

    expect(tree.root.findAllByProps({ testID: "travel-carousel" })).toHaveLength(0);
  });
});

describe("TravelScreen photo answer", () => {
  it("답변 바에 보낸 사진을 함께 건다", async () => {
    useConversation.setState({ turns: [photoAnsweredTurn], busy: false });
    const tree = await mount();

    expect(answerBar(tree).props.photoUri).toBe(PHOTO.uri);
  });

  it("글로만 물은 턴에는 사진이 붙지 않는다", async () => {
    useConversation.setState({ turns: [answeredTurn], busy: false });
    const tree = await mount();

    expect(answerBar(tree).props.photoUri).toBeNull();
  });
});

describe("TravelScreen follow-up context", () => {
  it("carries the previous answer with a typed follow-up", async () => {
    useConversation.setState({ turns: [answeredTurn], busy: false });
    const tree = await mount();

    await type(tree, "거기 근처 카페는?");
    await press(tree, "travel-send");

    const sent = askAgentMock.mock.calls[0][0];
    expect(sent.question).toBe("거기 근처 카페는?");
    expect(sent.context.intent).toEqual(INTENT);
  });

  it("포커스한 카드를 문맥의 초점으로 함께 보낸다", async () => {
    useConversation.setState({ turns: [mapTurn], busy: false });
    const tree = await mount();
    await swipeTo(tree, 1);

    await type(tree, "주차 가능해?");
    await press(tree, "travel-send");

    expect(askAgentMock.mock.calls[0][0].context.focusContentId).toBe("126509");
  });

  it("keeps the context on the turn so a retry resends it", async () => {
    useConversation.setState({ turns: [answeredTurn], busy: false });
    const tree = await mount();

    await type(tree, "거기 근처 카페는?");
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

    await press(tree, "travel-retry");

    expect(askAgentMock.mock.calls[0][0].context?.spots).toEqual([
      { contentId: "a", title: "무릉계곡" },
    ]);
  });

  it("sends no context on the very first question", async () => {
    const tree = await mount();

    await type(tree, "제주 계곡");
    await press(tree, "travel-send");

    expect(askAgentMock.mock.calls[0][0].context).toBeNull();
  });
});

describe("TravelScreen map", () => {
  it("pins the newest answer on the background map — no separate map route", async () => {
    const { router } = jest.requireMock("expo-router") as { router: { push: jest.Mock } };
    useConversation.setState({ turns: [mapTurn], busy: false });
    const tree = await mount();

    expect(mapView(tree).props.pins.map((p: { contentId: string }) => p.contentId)).toEqual([
      "126508",
      "126509",
      "126510",
    ]);
    expect(router.push).not.toHaveBeenCalled();
  });

  it("leaves the map bare when the answer carries no coordinates", async () => {
    useConversation.setState({ turns: [answeredTurn], busy: false });
    const tree = await mount();

    expect(mapView(tree).props.pins).toHaveLength(0);
    expect(mapView(tree).props.fit).toBeNull();
  });

  it("독과 캐러셀이 덮는 만큼 지도 여백을 비운다", async () => {
    useConversation.setState({ turns: [mapTurn], busy: false });
    const tree = await mount();

    const pad = mapView(tree).props.fit.pad;
    expect(pad.top).toBe(44 + 96);
    expect(pad.left).toBe(40);
    expect(pad.bottom).toBe(
      dockBasePx({ primer: false, attached: false, chips: false }) +
        panelBasePx({ chips: true, carousel: true }) +
        CAROUSEL_BLOCK_PX +
        24,
    );
  });

  it("이전 답의 핀은 남기지 않는다", async () => {
    useConversation.setState({ turns: [mapTurn, answeredTurn], busy: false });
    const tree = await mount();

    expect(mapView(tree).props.pins).toHaveLength(0);
  });
});

describe("TravelScreen retry", () => {
  it("resends intent and patch when a failed refine turn is retried", async () => {
    useConversation.setState({ turns: [failedRefineTurn], busy: false, activeId: null });
    const tree = await mount();
    await press(tree, "travel-retry");

    expect(askAgentMock).toHaveBeenCalledTimes(1);
    const input = askAgentMock.mock.calls[0][0];
    expect(input.intent).toEqual(INTENT);
    expect(input.patch).toEqual({ indoorOnly: true });
    expect(input.question).toBeFalsy();
    expect(useConversation.getState().turns).toHaveLength(1);
  });

  it("retries a photo refine with the same payload in the original turn", async () => {
    const failedPhotoRefine: Turn = {
      ...failedRefineTurn,
      id: "seed-photo-failed",
      photo: PHOTO,
    };
    useConversation.setState({ turns: [failedPhotoRefine], busy: false, activeId: null });
    const tree = await mount();
    await press(tree, "travel-retry");

    expect(askAgentMock.mock.calls[0][0]).toEqual({
      question: "",
      photo: PHOTO,
      intent: INTENT,
      patch: { indoorOnly: true },
      anchor: null,
      context: null,
      coords: COORDS,
    });
    const turns = useConversation.getState().turns;
    expect(turns).toHaveLength(1);
    expect(turns[0].id).toBe("seed-photo-failed");
  });

  it("resends the original text when a failed plain question turn is retried", async () => {
    useConversation.setState({
      turns: [{ ...answeredTurn, status: "failed", answer: null, errorMessage: "실패" }],
      busy: false,
      activeId: null,
    });
    const tree = await mount();
    await press(tree, "travel-retry");

    expect(askAgentMock).toHaveBeenCalledTimes(1);
    const input = askAgentMock.mock.calls[0][0];
    expect(input.question).toBe("여름에 시원한 계곡");
    expect(input.intent).toBeFalsy();
    expect(input.patch).toBeFalsy();
  });

  it("실패한 턴에는 단계 표시 없이 다시 시도만 남는다", async () => {
    useConversation.setState({ turns: [failedRefineTurn], busy: false, activeId: null });
    const tree = await mount();

    expect(answerBar(tree).props.step).toBeNull();
    expect(answerBar(tree).props.errorMessage).toBe("답을 만들지 못했어요.");
    expect(pressable(tree, "travel-retry")).toBeDefined();
  });

  it("다시 시도는 이전 스크롤 지시를 끌고 가지 않는다", async () => {
    jest.spyOn(FlatList.prototype, "scrollToOffset").mockImplementation(() => {});
    useConversation.setState({ turns: [mapTurn], busy: false });
    const tree = await mount();
    await act(async () => mapView(tree).props.onPinTap("126510"));
    expect(carousel(tree).props.scrollToIndex).toBe(2);

    await act(async () => {
      useConversation.setState({
        turns: [{ ...mapTurn, status: "failed", answer: null, errorMessage: "실패" }],
        busy: false,
        activeId: null,
      });
    });
    askAgentMock.mockResolvedValueOnce({ ...ANSWER, spots: PINNED });
    await press(tree, "travel-retry");

    expect(carousel(tree).props.focusedIndex).toBe(0);
    expect(carousel(tree).props.scrollToIndex).toBeNull();
  });
});

describe("TravelScreen save toast", () => {
  const conversationTurn: Turn = {
    ...answeredTurn,
    id: "save-turn",
    answer: {
      ...ANSWER,
      spots: [
        {
          contentId: "conversation-1",
          title: "대화 여행지",
          regionLabel: "부산",
          imageUrl: null,
          tag: null,
          lat: null,
          lng: null,
        },
      ],
    },
  };

  it("shows a saved toast from a card after the mutation succeeds", async () => {
    useConversation.setState({ turns: [conversationTurn], busy: false });
    toggleSave.mockResolvedValueOnce(true);
    const tree = await mount();
    await pressSave(tree, "conversation-1");
    expect(rendered(tree)).toContain("여행지를 저장했어요");
  });

  it("shows an unsaved toast from a card after the mutation succeeds", async () => {
    useConversation.setState({ turns: [conversationTurn], busy: false });
    toggleSave.mockResolvedValueOnce(false);
    const tree = await mount();
    await pressSave(tree, "conversation-1");
    expect(rendered(tree)).toContain("여행지 저장을 해제했어요");
  });

  it.each(["guest", "error"])("shows no save toast when toggle returns null for %s", async () => {
    useConversation.setState({ turns: [conversationTurn], busy: false });
    toggleSave.mockResolvedValueOnce(null);
    const tree = await mount();
    await pressSave(tree, "conversation-1");
    const out = rendered(tree);
    expect(out).not.toContain("여행지를 저장했어요");
    expect(out).not.toContain("여행지 저장을 해제했어요");
  });
});

describe("TravelScreen carousel stability", () => {
  it("결과가 없는 답에도 같은 빈 배열을 계속 넘긴다", async () => {
    useConversation.setState({ turns: [answeredTurn], busy: false });
    const tree = await mount();
    const before = carousel(tree).props.spots;

    await type(tree, "제주");

    expect(carousel(tree).props.spots).toBe(before);
    expect(before).toHaveLength(0);
  });

  it("답이 그대로면 같은 결과 배열을 계속 넘긴다", async () => {
    useConversation.setState({ turns: [mapTurn], busy: false });
    const tree = await mount();
    const before = carousel(tree).props.spots;

    await type(tree, "제주");

    expect(carousel(tree).props.spots).toBe(before);
  });

  it("씨앗 스팟이 그대로면 같은 한 장 배열을 계속 넘긴다", async () => {
    useTravelAnchor.setState({ spot: SEED });
    const tree = await mount();
    const before = carousel(tree).props.spots;

    await type(tree, "제주");

    expect(carousel(tree).props.spots).toBe(before);
  });
});

describe("TravelScreen 스팟 상세에서 넘어온 앵커", () => {
  it("씨앗 스팟 한 장을 캐러셀에 그린다", async () => {
    useTravelAnchor.setState({ spot: SEED });
    const tree = await mount();

    expect(carousel(tree).props.spots).toEqual([SEED]);
    expect(rendered(tree)).toContain("성산일출봉");
  });

  it("씨앗 스팟 이름으로 플레이스홀더와 문맥 칩을 세운다", async () => {
    useTravelAnchor.setState({ spot: SEED });
    const tree = await mount();

    expect(placeholder(tree)).toBe("성산일출봉에 대해 물어보기");
    expect(chip(tree, "성산일출봉 근처 카페")).toBeDefined();
  });

  it("씨앗 스팟을 지도 핀이자 중심으로 넘긴다", async () => {
    useTravelAnchor.setState({ spot: SEED });
    const tree = await mount();

    expect(mapView(tree).props.pins.map((p: { contentId: string }) => p.contentId)).toEqual([
      "126511",
    ]);
    expect(mapView(tree).props.center).toEqual({ lat: 33.46, lng: 126.94 });
    expect(mapView(tree).props.anchorId).toBe("126511");
  });

  it("질문을 보내면 씨앗을 비워 답 위로 살아남지 않는다", async () => {
    useTravelAnchor.setState({ spot: SEED });
    const tree = await mount();
    await type(tree, "근처 카페");
    await press(tree, "travel-send");

    expect(useTravelAnchor.getState().spot).toBeNull();
    expect(carousel(tree).props.spots).toEqual([]);
    expect(rendered(tree)).not.toContain("성산일출봉");
  });

  it("씨앗 스팟을 문맥 초점으로 실어 보낸다", async () => {
    useTravelAnchor.setState({ spot: SEED });
    const tree = await mount();
    await type(tree, "근처 카페");
    await press(tree, "travel-send");

    expect(askAgentMock.mock.calls[0][0].context).toEqual({
      spots: [],
      focusContentId: "126511",
    });
  });

  it("씨앗도 답도 없으면 패널 자체가 올라오지 않는다", async () => {
    const tree = await mount();

    expect(panelShown(tree)).toBe(false);
    expect(placeholder(tree)).toBe(ASK_PLACEHOLDER);
  });
});

describe("TravelScreen 이전 답이 남은 채 씨앗이 도착할 때", () => {
  it("살아남은 답 대신 씨앗 카드를 그린다", async () => {
    useConversation.setState({ turns: [mapTurn], busy: false });
    useTravelAnchor.setState({ spot: SEED });
    const tree = await mount();

    expect(carousel(tree).props.spots).toEqual([SEED]);
    expect(rendered(tree)).not.toContain("쇠소깍");
  });

  it("플레이스홀더도 씨앗 스팟을 부른다", async () => {
    useConversation.setState({ turns: [mapTurn], busy: false });
    useTravelAnchor.setState({ spot: SEED });
    const tree = await mount();

    expect(placeholder(tree)).toBe("성산일출봉에 대해 물어보기");
  });

  it("전송하면 이전 초점이 아니라 씨앗을 초점으로 보낸다", async () => {
    useConversation.setState({ turns: [mapTurn], busy: false });
    useTravelAnchor.setState({ spot: SEED });
    const tree = await mount();
    await type(tree, "근처 카페");
    await press(tree, "travel-send");

    const sent = askAgentMock.mock.calls[0][0];
    expect(sent.context.focusContentId).toBe("126511");
    expect(sent.context.spots).toEqual([]);
  });

  it("씨앗이 도착하면 낡은 답 바를 걷어낸다", async () => {
    useConversation.setState({ turns: [mapTurn], busy: false });
    useTravelAnchor.setState({ spot: SEED });
    const tree = await mount();

    expect(tree.root.findAllByType(AnswerBar)).toHaveLength(0);
    expect(useConversation.getState().turns).toEqual([]);
    expect(rendered(tree)).not.toContain("제주에서 한적한 곳");
  });

  it("0곳 답도 씨앗을 가리지 않는다", async () => {
    useConversation.setState({ turns: [answeredTurn], busy: false });
    useTravelAnchor.setState({ spot: SEED });
    const tree = await mount();

    expect(carousel(tree).props.spots).toEqual([SEED]);
    expect(placeholder(tree)).toBe("성산일출봉에 대해 물어보기");
  });

  it("씨앗을 소모한 뒤 시작한 턴은 지워지지 않는다", async () => {
    useConversation.setState({ turns: [mapTurn], busy: false });
    useTravelAnchor.setState({ spot: SEED });
    const tree = await mount();
    await type(tree, "근처 카페");
    await press(tree, "travel-send");

    expect(useTravelAnchor.getState().spot).toBeNull();
    expect(useConversation.getState().turns).toHaveLength(1);
    expect(answerBar(tree).props.question).toBe("근처 카페");
  });

  it("씨앗이 낡은 답 바를 걷어내므로 새 대화 버튼도 함께 사라진다", async () => {
    useConversation.setState({ turns: [mapTurn], busy: false });
    useTravelAnchor.setState({ spot: SEED });
    const tree = await mount();

    expect(pressable(tree, "travel-new-chat")).toBeUndefined();
  });

  it("3번째 카드를 보던 중 씨앗이 와도 씨앗을 초점으로 잡는다", async () => {
    useConversation.setState({ turns: [mapTurn], busy: false });
    const tree = await mount();
    await swipeTo(tree, 2);
    expect(carousel(tree).props.focusedIndex).toBe(2);

    await seed(SEED);

    expect(carousel(tree).props.focusedIndex).toBe(0);
    expect(carousel(tree).props.scrollToIndex).toBeNull();
    expect(placeholder(tree)).toBe("성산일출봉에 대해 물어보기");
    expect(chip(tree, "성산일출봉 근처 카페")).toBeDefined();
    expect(mapView(tree).props.anchorId).toBe("126511");
  });

  it("핀 탭으로 옮겨 둔 초점도 씨앗이 되돌린다", async () => {
    useConversation.setState({ turns: [mapTurn], busy: false });
    const tree = await mount();
    await act(async () => mapView(tree).props.onPinTap("126510"));
    expect(carousel(tree).props.focusedIndex).toBe(2);

    await seed(SEED);

    expect(carousel(tree).props.focusedIndex).toBe(0);
    expect(carousel(tree).props.scrollToIndex).toBeNull();
    expect(mapView(tree).props.anchorId).toBe("126511");
  });

  it("3번째 카드를 보던 중 온 씨앗도 문맥 초점으로 실려 나간다", async () => {
    useConversation.setState({ turns: [mapTurn], busy: false });
    const tree = await mount();
    await swipeTo(tree, 2);

    await seed(SEED);
    await type(tree, "근처 카페");
    await press(tree, "travel-send");

    expect(askAgentMock.mock.calls[0][0].context).toEqual({
      spots: [],
      focusContentId: "126511",
    });
  });

  it("씨앗이 붙은 렌더에는 낡은 답 바가 아예 나오지 않는다", async () => {
    useConversation.setState({ turns: [mapTurn], busy: false });
    const tree = await mount();
    expect(tree.root.findAllByType(AnswerBar)).toHaveLength(1);

    await seed(SEED);

    expect(tree.root.findAllByType(AnswerBar)).toHaveLength(0);
    expect(rendered(tree)).not.toContain("제주에서 한적한 곳");
  });

  it("대화가 스토어에 남아 있어도 씨앗 렌더는 답 바를 내지 않는다", async () => {
    useConversation.setState({ turns: [mapTurn], busy: false, clear: () => {} });
    const tree = await mount();
    expect(tree.root.findAllByType(AnswerBar)).toHaveLength(1);

    await seed(SEED);

    expect(useConversation.getState().turns).toHaveLength(1);
    expect(tree.root.findAllByType(AnswerBar)).toHaveLength(0);
    expect(carousel(tree).props.spots).toEqual([SEED]);
  });

  it("씨앗으로 시작한 대화를 새 대화로 다시 비울 수 있다", async () => {
    useConversation.setState({ turns: [mapTurn], busy: false });
    useTravelAnchor.setState({ spot: SEED });
    const tree = await mount();
    await type(tree, "근처 카페");
    await press(tree, "travel-send");
    await press(tree, "travel-new-chat");

    expect(useTravelAnchor.getState().spot).toBeNull();
    expect(useConversation.getState().turns).toEqual([]);
    expect(panelShown(tree)).toBe(false);
    expect(placeholder(tree)).toBe(ASK_PLACEHOLDER);
  });
});

describe("TravelScreen keyboard", () => {
  const handlers = new Map<string, (event: unknown) => void>();

  beforeEach(() => {
    handlers.clear();
    jest.spyOn(Keyboard, "addListener").mockImplementation(((
      event: string,
      handler: (payload: unknown) => void,
    ) => {
      handlers.set(event, handler);
      return { remove: () => handlers.delete(event) };
    }) as never);
  });

  async function fire(names: string[], payload: unknown) {
    const handler = names.map((name) => handlers.get(name)).find(Boolean);
    await act(async () => handler?.(payload));
  }

  const showKeyboard = (height: number) =>
    fire(["keyboardWillShow", "keyboardDidShow"], { endCoordinates: { height } });
  const hideKeyboard = () => fire(["keyboardWillHide", "keyboardDidHide"], {});

  it("lifts the dock above the keyboard so the field stays visible", async () => {
    const tree = await mount();
    expect(dockBottom(tree)).toBe(0);

    await showKeyboard(320);
    expect(dockBottom(tree)).toBe(320);
  });

  it("drops the dock back to the bottom when the keyboard closes", async () => {
    const tree = await mount();
    await showKeyboard(320);
    await hideKeyboard();

    expect(dockBottom(tree)).toBe(0);
  });

  it("lifts the result panel with the dock so the answer stays readable", async () => {
    useConversation.setState({ turns: [answeredTurn], busy: false });
    const tree = await mount();
    const resting = panelBottom(tree);

    await showKeyboard(320);
    expect(panelBottom(tree)).toBe(resting + 320);

    await hideKeyboard();
    expect(panelBottom(tree)).toBe(resting);
  });

  it("lifts the toast with the rest of the bottom stack", async () => {
    useConversation.setState({ turns: [answeredTurn], busy: false });
    const tree = await mount();
    const resting = toastBottom(tree);

    await showKeyboard(320);
    expect(toastBottom(tree)).toBe(resting + 320);
  });
});
