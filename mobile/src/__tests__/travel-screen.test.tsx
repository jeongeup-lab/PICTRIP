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
jest.mock("@/features/channels/queries", () => ({ useChannelCards: jest.fn() }));
jest.mock("@/features/travel/hooks/use-nearby-coords", () => ({ useNearbyCoords: jest.fn() }));
jest.mock("@/features/travel/usecases/pick-travel-photo", () => ({
  pickTravelPhoto: jest.fn(async () => null),
}));
jest.mock("@/features/travel/api", () => ({ askAgent: jest.fn() }));
jest.mock("@/features/saved/hooks/use-save-optimistic", () => ({
  useSaveOptimistic: () => ({ saved: false, toggle: jest.fn() }),
}));
jest.mock("@/features/spots/queries", () => ({ prefetchSpot: jest.fn() }));

const { useChannelCards } = jest.requireMock("@/features/channels/queries") as {
  useChannelCards: jest.Mock;
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
  suggestions: [{ label: "실내만", patch: { indoorOnly: true } }],
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
    suggestions: [{ label: "사람 적은 곳만", patch: { crowdPreference: "quiet" } }],
  },
  errorMessage: null,
  intent: null,
  patch: null,
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
};

let mounted: renderer.ReactTestRenderer | null = null;
let client: QueryClient;

beforeEach(() => {
  jest.clearAllMocks();
  useConversation.getState().clear();
  useChannelCards.mockReturnValue({ data: undefined, isError: true });
  useNearbyCoordsMock.mockReturnValue({ coords: COORDS, phase: "ready" });
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

async function press(tree: renderer.ReactTestRenderer, testID: string) {
  const node = pressable(tree, testID);
  if (!node) throw new Error(`no pressable with testID ${testID}`);
  await act(async () => node.props.onPress());
}

describe("TravelScreen starter chips", () => {
  it("offers the distance chip only when a location fix exists", async () => {
    const withFix = await mount();
    expect(pressable(withFix, "travel-chip-여기서 가까운 순")).toBeDefined();
    await act(async () => withFix.unmount());
    mounted = null;

    useNearbyCoordsMock.mockReturnValue({ coords: null, phase: "unavailable" });
    const withoutFix = await mount();
    expect(pressable(withoutFix, "travel-chip-여기서 가까운 순")).toBeUndefined();
    expect(pressable(withoutFix, "travel-chip-지금 열리는 축제")).toBeDefined();
  });

  it("sends a starter chip as a free-text question, never as a patch", async () => {
    const tree = await mount();
    await press(tree, "travel-chip-지금 열리는 축제");

    expect(askAgentMock).toHaveBeenCalledTimes(1);
    const input = askAgentMock.mock.calls[0][0];
    expect(input.question).toBe("지금 열리는 축제");
    expect(input.patch).toBeUndefined();
    expect(input.intent).toBeUndefined();
    expect(input.coords).toEqual(COORDS);
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

  it("sends the in-conversation refine chip as intent + patch, not as text", async () => {
    const tree = await mount();
    await press(tree, "answer-suggestion-실내만");

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

  it("refines the turn the chip sits under, not whatever answered last", async () => {
    const tree = await mount();
    await press(tree, "answer-suggestion-실내만");

    expect(askAgentMock).toHaveBeenCalledTimes(1);
    const input = askAgentMock.mock.calls[0][0];
    expect(input.intent).toEqual(INTENT);
    expect(input.intent).not.toEqual(NEWER_INTENT);
    expect(input.patch).toEqual({ indoorOnly: true });
  });

  it("still refines the newest answer from the composer rail, which owns no turn", async () => {
    const tree = await mount();
    await press(tree, "travel-chip-사람 적은 곳만");

    expect(askAgentMock).toHaveBeenCalledTimes(1);
    const input = askAgentMock.mock.calls[0][0];
    expect(input.intent).toEqual(NEWER_INTENT);
    expect(input.patch).toEqual({ crowdPreference: "quiet" });
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
