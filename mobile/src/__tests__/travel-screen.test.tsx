import renderer, { act } from "react-test-renderer";
import { Dimensions, FlatList, Keyboard, Text } from "react-native";
import { Image as ExpoImage } from "expo-image";
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
import { ChatTranscript, FAIL_TITLE } from "@/features/travel/components/ChatTranscript";
import {
  EmptyGreeting,
  GREETING_LINE1,
  SAMPLE_MOODS,
} from "@/features/travel/components/EmptyGreeting";
import { SpotCarousel } from "@/features/travel/components/SpotCarousel";
import { SearchPulse } from "@/features/travel/components/SearchPulse";
import { TravelSheet } from "@/features/travel/components/TravelSheet";
import { CARD_STRIDE } from "@/features/travel/components/SpotCard";
import { PHOTO_PICK_FAILED, PHOTO_SHOOT_FAILED } from "@/features/travel/lib/agent-errors";
import { ATTACH_HEADLINE, ATTACH_NOTICE } from "@/features/travel/components/TravelDock";
import { PHOTO_CHIP_LABEL, PHOTO_CHIP_TEST_ID } from "@/features/travel/components/ChipRow";
import { dockBasePx } from "@/features/travel/lib/screen-layout";
import { sheetHeightPx, type SheetSnap } from "@/features/travel/lib/sheet-layout";

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

const FRAME_H = Dimensions.get("window").height;
const DOCK_BASE = dockBasePx({ primer: false, attached: false });

function sheetPx(
  snap: SheetSnap,
  { dockPx = DOCK_BASE, keyboardPx = 0 }: { dockPx?: number; keyboardPx?: number } = {},
) {
  return (
    sheetHeightPx({ snap, frameH: FRAME_H, insetTop: 44, insetBottom: 34, keyboardPx, dockPx }) +
    keyboardPx
  );
}

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

const pendingTurn: Turn = {
  ...answeredTurn,
  id: "seed-pending",
  status: "pending",
  answer: null,
};

let mounted: renderer.ReactTestRenderer | null = null;
let client: QueryClient;

beforeEach(() => {
  jest.clearAllMocks();
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

function followChip(tree: renderer.ReactTestRenderer, label: string) {
  return tree.root
    .findAll(
      (node) =>
        typeof node.props.testID === "string" &&
        node.props.testID.startsWith("travel-follow-") &&
        typeof node.props.onPress === "function",
    )
    .find((node) => node.findAllByType(Text).some((text) => text.props.children === label));
}

async function pressFollow(tree: renderer.ReactTestRenderer, label: string) {
  const node = followChip(tree, label);
  if (!node) throw new Error(`no follow chip labeled ${label}`);
  await act(async () => node.props.onPress());
}

async function type(tree: renderer.ReactTestRenderer, text: string) {
  const input = tree.root.findByProps({ testID: "travel-input" });
  await act(async () => input.props.onChangeText(text));
}

async function focusInput(tree: renderer.ReactTestRenderer) {
  const input = tree.root.findByProps({ testID: "travel-input" });
  await act(async () => input.props.onFocus());
}

function placeholder(tree: renderer.ReactTestRenderer) {
  return tree.root.findByProps({ testID: "travel-input" }).props.placeholder;
}

function sheet(tree: renderer.ReactTestRenderer) {
  return tree.root.findByType(TravelSheet);
}

function snapOf(tree: renderer.ReactTestRenderer): SheetSnap {
  return sheet(tree).props.snap;
}

function carousel(tree: renderer.ReactTestRenderer) {
  const found = tree.root.findAllByType(SpotCarousel);
  return found[found.length - 1];
}

function mapView(tree: renderer.ReactTestRenderer) {
  return tree.root.findByType(KakaoWebMap);
}

function toastBottom(tree: renderer.ReactTestRenderer): number {
  return tree.root.findByProps({ testID: "travel-toast" }).props.bottom as number;
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

async function blankTap(tree: renderer.ReactTestRenderer) {
  await act(async () => mapView(tree).props.onBlankTap());
}

async function pressSave(tree: renderer.ReactTestRenderer, contentId: string) {
  await press(tree, `travel-card-save-${contentId}`);
}

describe("TravelScreen 시트 스냅", () => {
  it("처음에는 접힌 시트와 플로팅 칩만 있다", async () => {
    const tree = await mount();

    expect(snapOf(tree)).toBe("collapsed");
    expect(pressable(tree, "travel-sheet-grabber")).toBeUndefined();
    expect(chip(tree, "근처 맛집")).toBeDefined();
    expect(rendered(tree)).not.toContain(GREETING_LINE1);
  });

  it("입력에 포커스하면 시트가 올라오고 그리팅이 보인다", async () => {
    const tree = await mount();

    await focusInput(tree);

    expect(snapOf(tree)).toBe("mid");
    expect(pressable(tree, "travel-sheet-grabber")).toBeDefined();
    expect(rendered(tree)).toContain(GREETING_LINE1);
    expect(chip(tree, "근처 맛집")).toBeUndefined();
  });

  it("전송하는 동안 full, 답이 오면 mid 로 내려온다", async () => {
    let resolveAsk: (answer: AgentAnswer) => void = () => {};
    askAgentMock.mockReturnValueOnce(
      new Promise<AgentAnswer>((resolve) => {
        resolveAsk = resolve;
      }),
    );
    const tree = await mount();
    await type(tree, "제주 계곡");
    await press(tree, "travel-send");
    expect(snapOf(tree)).toBe("full");

    await act(async () => resolveAsk(ANSWER));

    expect(snapOf(tree)).toBe("mid");
  });

  it("실패한 턴은 full 에 남아 재시도를 보여준다", async () => {
    askAgentMock.mockRejectedValueOnce(new Error("boom"));
    const tree = await mount();

    await type(tree, "제주 계곡");
    await press(tree, "travel-send");

    expect(snapOf(tree)).toBe("full");
    expect(rendered(tree)).toContain(FAIL_TITLE);
    expect(pressable(tree, "travel-retry")).toBeDefined();
  });

  it("그래버 탭은 full 과 mid 를 오간다", async () => {
    const tree = await mount();
    await focusInput(tree);
    expect(snapOf(tree)).toBe("mid");

    await press(tree, "travel-sheet-grabber");
    expect(snapOf(tree)).toBe("full");

    await press(tree, "travel-sheet-grabber");
    expect(snapOf(tree)).toBe("mid");
  });

  it("상세에서 씨앗을 물고 들어오면 mid 로 열린다", async () => {
    useTravelAnchor.setState({ spot: SEED });
    const tree = await mount();

    expect(snapOf(tree)).toBe("mid");
  });

  it("응답 대기 펄스는 시트 높이 위에서 돈다", async () => {
    let resolveAsk: (answer: AgentAnswer) => void = () => {};
    askAgentMock.mockReturnValueOnce(
      new Promise<AgentAnswer>((resolve) => {
        resolveAsk = resolve;
      }),
    );
    const tree = await mount();
    await type(tree, "제주 계곡");
    await press(tree, "travel-send");

    const pulse = tree.root.findByType(SearchPulse);
    expect(pulse.props.active).toBe(true);
    expect(pulse.props.bottom).toBe(sheetPx("full"));

    await act(async () => resolveAsk(ANSWER));
  });
});

describe("TravelScreen 지도 탭", () => {
  it("지도를 탭하면 대화를 비우고 시트를 접는다", async () => {
    useConversation.setState({ turns: [mapTurn], busy: false });
    const tree = await mount();

    await blankTap(tree);

    expect(useConversation.getState().turns).toEqual([]);
    expect(snapOf(tree)).toBe("collapsed");
    expect(chip(tree, "근처 맛집")).toBeDefined();
    expect(placeholder(tree)).toBe(ASK_PLACEHOLDER);
  });

  it("응답을 기다리는 동안에는 대화를 지키고 키보드만 내린다", async () => {
    const dismiss = jest.spyOn(Keyboard, "dismiss").mockImplementation(() => {});
    useConversation.setState({ turns: [pendingTurn], busy: true, activeId: pendingTurn.id });
    const tree = await mount();

    await blankTap(tree);

    expect(dismiss).toHaveBeenCalled();
    expect(useConversation.getState().turns).toHaveLength(1);
  });

  it("씨앗도 지도 탭으로 비운다", async () => {
    useTravelAnchor.setState({ spot: SEED });
    const tree = await mount();

    await blankTap(tree);

    expect(useTravelAnchor.getState().spot).toBeNull();
    expect(snapOf(tree)).toBe("collapsed");
  });

  it("새 대화 뒤 다시 물으면 캐러셀이 첫 칸에서 시작한다", async () => {
    useConversation.setState({ turns: [mapTurn], busy: false });
    const tree = await mount();
    await swipeTo(tree, 2);
    await blankTap(tree);

    await act(async () => useConversation.setState({ turns: [mapTurn], busy: false }));

    expect(carousel(tree).props.focusedIndex).toBe(0);
    expect(carousel(tree).props.scrollToIndex).toBeNull();
  });

  it("핀 탭은 초기화가 아니라 포커스 이동이다", async () => {
    jest.spyOn(FlatList.prototype, "scrollToOffset").mockImplementation(() => {});
    useConversation.setState({ turns: [mapTurn], busy: false });
    const tree = await mount();

    await act(async () => mapView(tree).props.onPinTap("126509"));

    expect(useConversation.getState().turns).toHaveLength(1);
    expect(carousel(tree).props.focusedIndex).toBe(1);
  });
});

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
    const turns = useConversation.getState().turns;
    expect(turns[turns.length - 1].question).toBe("내 위치 근처 맛집");
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

  it("첫 화면 칩은 사진 뒤에 근처 세 갈래로 고정이다", async () => {
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

    expect(labels[0]).toBe(PHOTO_CHIP_LABEL);
    expect(labels).toEqual([PHOTO_CHIP_LABEL, "근처 카페", "근처 맛집", "근처 볼거리"]);
    expect(pressable(tree, PHOTO_CHIP_TEST_ID)).toBeDefined();
  });

  it("대화가 생기면 플로팅 칩이 사라진다", async () => {
    useConversation.setState({ turns: [answeredTurn], busy: false });
    const tree = await mount();

    expect(chip(tree, "근처 맛집")).toBeUndefined();
    expect(chip(tree, PHOTO_CHIP_LABEL)).toBeUndefined();
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

  it("첨부를 지우면 배너가 사라지고 칩 줄은 그대로다", async () => {
    pickTravelPhoto.mockResolvedValueOnce(PHOTO);
    const tree = await mount();
    await pressChip(tree, PHOTO_CHIP_LABEL);

    await press(tree, "travel-attach-clear");

    expect(tree.root.findAllByProps({ testID: "travel-attach-banner" })).toHaveLength(0);
    expect(chip(tree, PHOTO_CHIP_LABEL)).toBeDefined();
  });
});

describe("TravelScreen empty greeting", () => {
  it("샘플 무드를 누르면 그 문장이 질문으로 나간다", async () => {
    const tree = await mount();
    await focusInput(tree);

    await press(tree, "travel-sample-0");

    expect(askAgentMock).toHaveBeenCalledTimes(1);
    expect(askAgentMock.mock.calls[0][0].question).toBe(SAMPLE_MOODS[0].question);
    expect(snapOf(tree)).toBe("mid");
    const turns = useConversation.getState().turns;
    expect(turns[turns.length - 1].question).toBe(SAMPLE_MOODS[0].question);
  });

  it("앨범 CTA 는 사진을 골라 독 배너에 붙인다", async () => {
    pickTravelPhoto.mockResolvedValueOnce(PHOTO);
    const tree = await mount();
    await focusInput(tree);

    await press(tree, "travel-empty-album");

    expect(askAgentMock).not.toHaveBeenCalled();
    expect(tree.root.findAllByProps({ testID: "travel-attach-banner" }).length).toBeGreaterThan(0);
  });

  it("촬영 CTA 는 카메라 경로를 탄다", async () => {
    const shot = { uri: "file://shot.jpg", name: "shot.jpg", type: "image/jpeg" };
    shootTravelPhoto.mockResolvedValueOnce(shot);
    const tree = await mount();
    await focusInput(tree);

    await press(tree, "travel-empty-shoot");

    expect(shootTravelPhoto).toHaveBeenCalledTimes(1);
    expect(tree.root.findAllByProps({ testID: "travel-attach-banner" }).length).toBeGreaterThan(0);
  });

  it("대화가 생기면 그리팅 대신 트랜스크립트가 선다", async () => {
    useConversation.setState({ turns: [mapTurn], busy: false });
    const tree = await mount();
    await focusInput(tree);

    expect(rendered(tree)).not.toContain(GREETING_LINE1);
    expect(tree.root.findAllByType(EmptyGreeting)).toHaveLength(0);
    expect(tree.root.findAllByType(ChatTranscript)).toHaveLength(1);
  });
});

describe("TravelScreen transcript", () => {
  it("질문 말풍선과 답변 문장을 함께 그린다", async () => {
    useConversation.setState({ turns: [mapTurn], busy: false });
    const tree = await mount();

    const out = rendered(tree);
    expect(out).toContain("제주에서 한적한 곳");
    expect(out).toContain("조건에 맞는 곳으로 4곳 추렸어요");
  });

  it("답이 오기 전에는 진행 단계를 건다", async () => {
    useConversation.setState({ turns: [pendingTurn], busy: true, activeId: pendingTurn.id });
    const tree = await mount();

    expect(tree.root.findAllByProps({ testID: "travel-turn-step" }).length).toBeGreaterThan(0);
    expect(rendered(tree)).toContain("질문에서 조건 읽는 중");
  });

  it("실패한 턴에는 실패 제목과 다시 시도만 남는다", async () => {
    useConversation.setState({ turns: [failedRefineTurn], busy: false, activeId: null });
    const tree = await mount();

    const out = rendered(tree);
    expect(out).toContain(FAIL_TITLE);
    expect(out).toContain("답을 만들지 못했어요.");
    expect(pressable(tree, "travel-retry")).toBeDefined();
  });

  it("사진으로 물은 턴은 말풍선에 사진을 함께 건다", async () => {
    useConversation.setState({ turns: [photoAnsweredTurn], busy: false });
    const tree = await mount();

    const thumbs = tree.root.findAllByType(ExpoImage);
    expect(thumbs.some((thumb) => thumb.props.source?.uri === PHOTO.uri)).toBe(true);
  });

  it("결과가 없는 답은 캐러셀 없이 답변만 그린다", async () => {
    useConversation.setState({ turns: [answeredTurn], busy: false });
    const tree = await mount();

    expect(tree.root.findAllByType(SpotCarousel)).toHaveLength(0);
    expect(rendered(tree)).not.toContain(FAIL_TITLE);
    expect(pressable(tree, "travel-retry")).toBeUndefined();
  });
});

describe("TravelScreen carousel focus", () => {
  beforeEach(() => {
    useConversation.setState({ turns: [mapTurn], busy: false });
  });

  it("첫 카드가 곧바로 문맥이 된다", async () => {
    const tree = await mount();

    expect(carousel(tree).props.focusedIndex).toBe(0);
    expect(placeholder(tree)).toBe("무릉계곡에 대해 물어보기");
  });

  it("스와이프하면 플레이스홀더와 후속 질문이 따라 바뀐다", async () => {
    const tree = await mount();

    await swipeTo(tree, 1);

    expect(placeholder(tree)).toBe("천지연에 대해 물어보기");

    await pressFollow(tree, "여긴 어떤 곳이야?");

    expect(askAgentMock.mock.calls[0][0].question).toBe("천지연은 어떤 곳이야?");
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

  it("핀을 누르면 캐러셀을 그 카드로 스크롤한다", async () => {
    const scrollToOffset = jest
      .spyOn(FlatList.prototype, "scrollToOffset")
      .mockImplementation(() => {});
    const tree = await mount();

    await act(async () => mapView(tree).props.onPinTap("126509"));

    expect(scrollToOffset).toHaveBeenCalledWith({ offset: CARD_STRIDE, animated: true });
    expect(carousel(tree).props.focusedIndex).toBe(1);
    expect(carousel(tree).props.scrollToIndex).toBe(1);
    expect(mapView(tree).props.center).toEqual({ lat: 33.25, lng: 126.56 });
  });

  it("핀 탭으로 옮긴 문맥이 플레이스홀더에도 반영된다", async () => {
    jest.spyOn(FlatList.prototype, "scrollToOffset").mockImplementation(() => {});
    const tree = await mount();

    await act(async () => mapView(tree).props.onPinTap("126509"));

    expect(placeholder(tree)).toBe("천지연에 대해 물어보기");
  });

  it("지도에 없는 스팟의 핀 탭은 무시한다", async () => {
    const tree = await mount();

    await act(async () => mapView(tree).props.onPinTap("999999"));

    expect(carousel(tree).props.focusedIndex).toBe(0);
    expect(carousel(tree).props.scrollToIndex).toBeNull();
  });
});

describe("TravelScreen follow-up chips", () => {
  it("답이 내려앉으면 루트 후속 칩이 붙는다", async () => {
    useConversation.setState({ turns: [mapTurn], busy: false });
    const tree = await mount();

    expect(followChip(tree, "근처 뭐 있어?")).toBeDefined();
    expect(followChip(tree, "여긴 어떤 곳이야?")).toBeDefined();
  });

  it("근처 분기로 들어갔다 뒤로 나올 수 있다", async () => {
    useConversation.setState({ turns: [mapTurn], busy: false });
    const tree = await mount();

    await pressFollow(tree, "근처 뭐 있어?");

    expect(askAgentMock).not.toHaveBeenCalled();
    for (const label of ["카페", "맛집", "볼거리", "‹ 뒤로"]) {
      expect(followChip(tree, label)).toBeDefined();
    }

    await pressFollow(tree, "‹ 뒤로");

    expect(followChip(tree, "근처 뭐 있어?")).toBeDefined();
  });

  it("근처 칩은 포커스한 카드의 앵커로 나가고 라벨 문장이 말풍선이 된다", async () => {
    useConversation.setState({ turns: [mapTurn], busy: false });
    const tree = await mount();

    await pressFollow(tree, "근처 뭐 있어?");
    await pressFollow(tree, "카페");

    expect(askAgentMock).toHaveBeenCalledTimes(1);
    expect(askAgentMock.mock.calls[0][0].anchor).toEqual({
      contentId: "126508",
      action: "cafe",
    });
    const turns = useConversation.getState().turns;
    expect(turns[turns.length - 1].question).toBe("무릉계곡 근처 카페");
  });

  it("정보 칩은 followKey 와 초점 문맥을 실어 보낸다", async () => {
    useConversation.setState({ turns: [mapTurn], busy: false });
    const tree = await mount();

    await pressFollow(tree, "여긴 어떤 곳이야?");

    const input = askAgentMock.mock.calls[0][0];
    expect(input.question).toBe("무릉계곡은 어떤 곳이야?");
    expect(input.context.focusContentId).toBe("126508");
    const turns = useConversation.getState().turns;
    expect(turns[turns.length - 1].followKey).toBe("about");
  });

  it("이미 물은 정보는 빠지고 연관 관광지는 앵커로 나간다", async () => {
    const aboutTurn: Turn = {
      ...answeredTurn,
      id: "asked-about",
      followKey: "about",
      context: { spots: [], focusContentId: "126508" },
    };
    const hoursTurn: Turn = {
      ...answeredTurn,
      id: "asked-hours",
      followKey: "hours",
      context: { spots: [], focusContentId: "126508" },
    };
    useConversation.setState({ turns: [aboutTurn, hoursTurn, mapTurn], busy: false });
    const tree = await mount();

    expect(followChip(tree, "여긴 어떤 곳이야?")).toBeUndefined();
    expect(followChip(tree, "영업시간은?")).toBeUndefined();
    expect(followChip(tree, "연관 관광지는?")).toBeDefined();

    await pressFollow(tree, "연관 관광지는?");

    expect(askAgentMock.mock.calls[0][0].anchor).toEqual({
      contentId: "126508",
      action: "related",
    });
    const turns = useConversation.getState().turns;
    expect(turns[turns.length - 1].question).toBe("무릉계곡 연관 관광지는?");
  });

  it("서버 refinement 는 intent + patch 로 나간다", async () => {
    const refinedTurn: Turn = {
      ...mapTurn,
      id: "refined",
      answer: {
        ...mapTurn.answer!,
        suggestions: [],
        refinements: [{ label: "실내만", patch: { indoorOnly: true } }],
      },
    };
    useConversation.setState({ turns: [refinedTurn], busy: false });
    const tree = await mount();

    await pressFollow(tree, "실내만");

    expect(askAgentMock).toHaveBeenCalledTimes(1);
    const input = askAgentMock.mock.calls[0][0];
    expect(input.patch).toEqual({ indoorOnly: true });
    expect(input.intent).toEqual(INTENT);
    expect(input.question).toBeFalsy();
    const turns = useConversation.getState().turns;
    expect(turns[turns.length - 1].question).toBe("실내만");
  });

  it("사진 턴의 refinement 는 원본 사진을 끌고 간다", async () => {
    const photoMapTurn: Turn = {
      ...photoAnsweredTurn,
      answer: {
        ...ANSWER,
        spots: PINNED,
        suggestions: [],
        refinements: [{ label: "실내만", patch: { indoorOnly: true } }],
      },
    };
    useConversation.setState({ turns: [photoMapTurn], busy: false });
    const tree = await mount();

    await pressFollow(tree, "실내만");

    const input = askAgentMock.mock.calls[0][0];
    expect(input.photo).toEqual(PHOTO);
    expect(input.intent).toEqual(INTENT);
    expect(input.patch).toEqual({ indoorOnly: true });
  });

  it("서버 suggestion 은 질문 그대로 나간다", async () => {
    const suggestTurn: Turn = {
      ...mapTurn,
      id: "suggest",
      answer: { ...mapTurn.answer!, refinements: [], suggestions: ["야경 좋은 곳도 볼래?"] },
    };
    useConversation.setState({ turns: [suggestTurn], busy: false });
    const tree = await mount();

    await pressFollow(tree, "야경 좋은 곳도 볼래?");

    const input = askAgentMock.mock.calls[0][0];
    expect(input.question).toBe("야경 좋은 곳도 볼래?");
    expect(input.context.intent).toEqual(INTENT);
  });

  it("결과가 없는 검색 답은 정보 분기가 아니라 루트 후속으로 남는다", async () => {
    useConversation.setState({ turns: [answeredTurn], busy: false });
    const tree = await mount();

    expect(rendered(tree)).toContain("내 위치 근처의 카페·맛집·볼거리를 찾아드릴 수 있어요.");
    expect(rendered(tree)).not.toContain("더 궁금한 게 있으세요?");
    expect(followChip(tree, "여긴 어떤 곳이야?")).toBeUndefined();
    expect(followChip(tree, "근처 뭐 있어?")).toBeDefined();
    expect(followChip(tree, "실내만")).toBeDefined();
  });

  it("followKey 턴 뒤에는 정보 분기가 열린다", async () => {
    const detailTurn: Turn = {
      ...mapTurn,
      id: "seed-detail",
      followKey: "about",
      context: { spots: [], focusContentId: "126508" },
    };
    useConversation.setState({ turns: [detailTurn], busy: false });
    const tree = await mount();

    expect(rendered(tree)).toContain("더 궁금한 게 있으세요?");
    expect(followChip(tree, "영업시간은?")).toBeDefined();
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

  it("접힌 시트가 덮는 만큼만 지도 여백을 비운다", async () => {
    useConversation.setState({ turns: [mapTurn], busy: false });
    const tree = await mount();

    const pad = mapView(tree).props.fit.pad;
    expect(pad.top).toBe(44 + 96);
    expect(pad.left).toBe(40);
    expect(pad.bottom).toBe(sheetPx("collapsed") + 24);
  });

  it("시트가 올라오면 지도 여백도 함께 커진다", async () => {
    useConversation.setState({ turns: [mapTurn], busy: false });
    const tree = await mount();

    await focusInput(tree);

    expect(mapView(tree).props.fit.pad.bottom).toBe(sheetPx("mid") + 24);
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

describe("TravelScreen 질의 중 잠금", () => {
  it("응답을 기다리는 동안 전송을 막는다", async () => {
    useConversation.setState({ turns: [pendingTurn], busy: true, activeId: pendingTurn.id });
    const tree = await mount();

    await type(tree, "제주 계곡");
    await press(tree, "travel-send");

    expect(askAgentMock).not.toHaveBeenCalled();
    expect(useConversation.getState().turns).toHaveLength(1);
  });

  it("응답을 기다리는 동안 입력이 잠긴다", async () => {
    useConversation.setState({ turns: [pendingTurn], busy: true, activeId: pendingTurn.id });
    const tree = await mount();

    expect(tree.root.findByProps({ testID: "travel-input" }).props.editable).toBe(false);
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

  it("shows a saved toast lifted above the sheet after the mutation succeeds", async () => {
    useConversation.setState({ turns: [conversationTurn], busy: false });
    toggleSave.mockResolvedValueOnce(true);
    const tree = await mount();
    await pressSave(tree, "conversation-1");

    expect(rendered(tree)).toContain("여행지를 저장했어요");
    expect(toastBottom(tree)).toBe(sheetPx("collapsed") + 12);
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

describe("TravelScreen 스팟 상세에서 넘어온 앵커", () => {
  it("씨앗 스팟을 지도 핀이자 중심으로 넘긴다", async () => {
    useTravelAnchor.setState({ spot: SEED });
    const tree = await mount();

    expect(mapView(tree).props.pins.map((p: { contentId: string }) => p.contentId)).toEqual([
      "126511",
    ]);
    expect(mapView(tree).props.center).toEqual({ lat: 33.46, lng: 126.94 });
    expect(mapView(tree).props.anchorId).toBe("126511");
  });

  it("씨앗 스팟 이름으로 플레이스홀더를 세우고 그리팅을 연다", async () => {
    useTravelAnchor.setState({ spot: SEED });
    const tree = await mount();

    expect(placeholder(tree)).toBe("성산일출봉에 대해 물어보기");
    expect(rendered(tree)).toContain(GREETING_LINE1);
  });

  it("질문을 보내면 씨앗을 비워 답 위로 살아남지 않는다", async () => {
    useTravelAnchor.setState({ spot: SEED });
    const tree = await mount();
    await type(tree, "근처 카페");
    await press(tree, "travel-send");

    expect(useTravelAnchor.getState().spot).toBeNull();
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

  it("이전 답이 남은 채 씨앗이 오면 낡은 대화를 걷어낸다", async () => {
    useConversation.setState({ turns: [mapTurn], busy: false });
    useTravelAnchor.setState({ spot: SEED });
    const tree = await mount();

    expect(useConversation.getState().turns).toEqual([]);
    expect(mapView(tree).props.pins.map((p: { contentId: string }) => p.contentId)).toEqual([
      "126511",
    ]);
    expect(placeholder(tree)).toBe("성산일출봉에 대해 물어보기");
    expect(rendered(tree)).not.toContain("제주에서 한적한 곳");
  });

  it("3번째 카드를 보던 중 씨앗이 와도 씨앗을 초점으로 잡는다", async () => {
    useConversation.setState({ turns: [mapTurn], busy: false });
    const tree = await mount();
    await swipeTo(tree, 2);
    expect(carousel(tree).props.focusedIndex).toBe(2);

    await seed(SEED);

    expect(placeholder(tree)).toBe("성산일출봉에 대해 물어보기");
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

  it("씨앗을 소모한 뒤 시작한 턴은 지워지지 않는다", async () => {
    useConversation.setState({ turns: [mapTurn], busy: false });
    useTravelAnchor.setState({ spot: SEED });
    const tree = await mount();
    await type(tree, "근처 카페");
    await press(tree, "travel-send");

    expect(useTravelAnchor.getState().spot).toBeNull();
    const turns = useConversation.getState().turns;
    expect(turns).toHaveLength(1);
    expect(turns[0].question).toBe("근처 카페");
  });

  it("씨앗으로 시작한 대화를 지도 탭으로 다시 비울 수 있다", async () => {
    useConversation.setState({ turns: [mapTurn], busy: false });
    useTravelAnchor.setState({ spot: SEED });
    const tree = await mount();
    await type(tree, "근처 카페");
    await press(tree, "travel-send");
    await blankTap(tree);

    expect(useTravelAnchor.getState().spot).toBeNull();
    expect(useConversation.getState().turns).toEqual([]);
    expect(snapOf(tree)).toBe("collapsed");
    expect(placeholder(tree)).toBe(ASK_PLACEHOLDER);
  });

  it("씨앗도 답도 없으면 시트는 접혀 있고 그리팅도 없다", async () => {
    const tree = await mount();

    expect(snapOf(tree)).toBe("collapsed");
    expect(rendered(tree)).not.toContain(GREETING_LINE1);
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

  it("키보드가 올라오면 접힌 시트만큼의 지도 여백도 같이 올라간다", async () => {
    useConversation.setState({ turns: [mapTurn], busy: false });
    const tree = await mount();
    expect(mapView(tree).props.fit.pad.bottom).toBe(sheetPx("collapsed") + 24);

    await showKeyboard(320);
    expect(mapView(tree).props.fit.pad.bottom).toBe(sheetPx("collapsed", { keyboardPx: 320 }) + 24);

    await hideKeyboard();
    expect(mapView(tree).props.fit.pad.bottom).toBe(sheetPx("collapsed") + 24);
  });

  it("mid 시트는 키보드 위 남은 높이에 맞춰 줄어든다", async () => {
    useConversation.setState({ turns: [mapTurn], busy: false });
    const tree = await mount();
    await focusInput(tree);
    await showKeyboard(320);

    expect(mapView(tree).props.fit.pad.bottom).toBe(sheetPx("mid", { keyboardPx: 320 }) + 24);
  });
});
