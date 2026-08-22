import renderer, { act } from "react-test-renderer";
import { ActionSheetIOS } from "react-native";
import TravelScreen, { NEW_CHAT_LABEL, WORDMARK } from "@/app/(tabs)/travel";
import {
  streamChat,
  type ChatDoneEvent,
  type ChatHandlers,
  type ChatInput,
  type TravelSpot,
} from "@/features/travel/api";
import { FAIL_TITLE } from "@/features/travel/components/AssistantTurn";
import { ASK_PLACEHOLDER, STREAMING_PLACEHOLDER } from "@/features/travel/components/ChatComposer";
import { SpotCarousel } from "@/features/travel/components/SpotCarousel";
import { PHOTO_ONLY_QUESTION } from "@/features/travel/lib/question";
import { useChat } from "@/features/travel/stores/chat-store";
import { useNearbyCoords } from "@/features/travel/hooks/use-nearby-coords";

jest.mock("expo-router", () => ({ router: { push: jest.fn(), back: jest.fn() } }));
jest.mock("react-native-safe-area-context", () => ({
  SafeAreaView: (props: { children?: unknown }) => props.children,
  useSafeAreaInsets: () => ({ top: 44, bottom: 34, left: 0, right: 0 }),
}));
jest.mock("@/features/travel/api", () => ({ streamChat: jest.fn() }));
jest.mock("@/features/travel/hooks/use-nearby-coords", () => ({ useNearbyCoords: jest.fn() }));
jest.mock("@/features/travel/usecases/pick-travel-photo", () => ({
  pickTravelPhoto: jest.fn(async () => null),
  shootTravelPhoto: jest.fn(async () => null),
}));
jest.mock("@/features/travel/components/WelcomeBubble", () => ({
  WelcomeBubble: () => null,
  WELCOME_TEXT: "",
}));
jest.mock("@/features/saved/hooks/use-save-optimistic", () => ({
  useSaveOptimistic: () => ({ saved: false, toggle: jest.fn(async () => true) }),
}));
jest.mock("@/features/spots/queries", () => ({ prefetchSpot: jest.fn() }));
jest.mock("@/lib/storage", () => ({
  getAiTransferConsent: jest.fn(async () => true),
  setAiTransferConsent: jest.fn(async () => {}),
}));
jest.mock("@/features/consent/api", () => ({ putAiTransferConsent: jest.fn(async () => ({})) }));
jest.mock("@/features/consent/queries", () => ({ useConsents: () => ({ data: undefined }) }));

const storageMock = jest.requireMock("@/lib/storage") as {
  getAiTransferConsent: jest.Mock;
  setAiTransferConsent: jest.Mock;
};
const streamChatMock = streamChat as jest.Mock;
const useNearbyCoordsMock = useNearbyCoords as jest.Mock;
const { pickTravelPhoto } = jest.requireMock("@/features/travel/usecases/pick-travel-photo") as {
  pickTravelPhoto: jest.Mock;
};

const COORDS = { lat: 37.5665, lng: 126.978 };
const PHOTO = { uri: "file:///a.jpg", name: "a.jpg", type: "image/jpeg" };

const SPOTS: TravelSpot[] = [
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

const DONE: ChatDoneEvent = {
  answerText: "제주라면 **무릉계곡**이 좋아요.\n- 아침에 한적해요",
  spots: SPOTS,
  sources: [{ kind: "naver_blog", title: "제주 계곡 후기", url: "https://blog", date: "20260801" }],
  intent: { categoryKeywords: ["계곡"], regionHints: ["제주"] },
  totalCount: 4,
};

interface Stream {
  input: ChatInput;
  handlers: ChatHandlers;
  end: () => void;
}

let streams: Stream[];
let mounted: renderer.ReactTestRenderer | null = null;

beforeEach(() => {
  jest.clearAllMocks();
  streams = [];
  useChat.setState({ turns: [], streaming: false, activeId: null, issued: 0 });
  useNearbyCoordsMock.mockReturnValue({
    coords: COORDS,
    phase: "ready",
    askable: false,
    ask: jest.fn(),
  });
  streamChatMock.mockImplementation(
    (input: ChatInput, handlers: ChatHandlers) =>
      new Promise<void>((resolve) => {
        streams.push({ input, handlers, end: resolve });
      }),
  );
});

afterEach(async () => {
  const tree = mounted;
  mounted = null;
  if (tree) await act(async () => tree.unmount());
  jest.restoreAllMocks();
});

async function mount() {
  await act(async () => {
    mounted = renderer.create(<TravelScreen />);
  });
  return mounted!;
}

function rendered(tree: renderer.ReactTestRenderer) {
  return JSON.stringify(tree.toJSON());
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

function input(tree: renderer.ReactTestRenderer) {
  return tree.root.findByProps({ testID: "travel-input" });
}

async function type(tree: renderer.ReactTestRenderer, text: string) {
  await act(async () => input(tree).props.onChangeText(text));
}

async function send(tree: renderer.ReactTestRenderer, text: string) {
  await type(tree, text);
  await press(tree, "travel-send");
}

async function finishLast() {
  const stream = streams[streams.length - 1];
  await act(async () => {
    stream.handlers.onDone?.(DONE);
    stream.end();
  });
}

describe("TravelScreen 워드마크와 전송", () => {
  it("상단에 PICTRIP 워드마크가 선다", async () => {
    const tree = await mount();

    expect(rendered(tree)).toContain(WORDMARK);
    expect(pressable(tree, "travel-new-chat")).toBeDefined();
    expect(input(tree).props.placeholder).toBe(ASK_PLACEHOLDER);
  });

  it("전송하면 사용자 말풍선이 서고 streamChat이 좌표와 함께 나간다", async () => {
    const tree = await mount();

    await send(tree, "제주 계곡");

    expect(rendered(tree)).toContain("제주 계곡");
    expect(streamChatMock).toHaveBeenCalledTimes(1);
    const sent = streams[0].input;
    expect(sent.message).toBe("제주 계곡");
    expect(sent.coords).toEqual(COORDS);
    expect(sent.clientTime).toBeTruthy();
    expect(sent.context).toBeNull();
    expect(sent.history).toEqual([]);
  });

  it("스트리밍 중에는 입력이 잠기고 안내 플레이스홀더가 선다", async () => {
    const tree = await mount();
    await send(tree, "제주 계곡");

    expect(input(tree).props.editable).toBe(false);
    expect(input(tree).props.placeholder).toBe(STREAMING_PLACEHOLDER);

    await finishLast();

    expect(input(tree).props.editable).toBe(true);
    expect(input(tree).props.placeholder).toBe("무릉계곡에 대해 물어보세요");
  });

  it("delta가 오는 대로 본문이 자란다", async () => {
    const tree = await mount();
    await send(tree, "제주 계곡");

    await act(async () => streams[0].handlers.onDelta?.("제주라면 "));
    await act(async () => streams[0].handlers.onDelta?.("무릉계곡이요."));

    expect(rendered(tree)).toContain("제주라면 무릉계곡이요.");
  });

  it("step은 같은 index로 run에서 done으로 바뀐다", async () => {
    const tree = await mount();
    await send(tree, "제주 계곡");

    await act(async () =>
      streams[0].handlers.onStep?.({ index: 0, label: "조건 읽는 중", status: "run" }),
    );
    await act(async () =>
      streams[0].handlers.onStep?.({
        index: 0,
        label: "조건 읽는 중",
        badge: "계곡",
        status: "done",
      }),
    );

    expect(tree.root.findAllByProps({ testID: "travel-turn-step" }).length).toBeGreaterThan(0);
    expect(rendered(tree)).toContain("조건 읽는 중");
    expect(rendered(tree)).toContain("계곡");
  });
});

describe("TravelScreen 완료 턴", () => {
  it("done이 내려앉으면 캐러셀과 출처가 선다", async () => {
    const tree = await mount();
    await send(tree, "제주 계곡");
    await finishLast();

    expect(tree.root.findAllByType(SpotCarousel)).toHaveLength(1);
    expect(pressable(tree, "travel-sources")).toBeDefined();
    expect(rendered(tree)).toContain("무릉계곡");
  });

  it("앵커 줄은 카드가 있는 최신 턴에만 선다", async () => {
    const tree = await mount();
    await send(tree, "제주 계곡");
    await finishLast();

    expect(tree.root.findAllByProps({ testID: "travel-anchor-row" }).length).toBeGreaterThan(0);

    await send(tree, "서울은?");
    await act(async () => {
      streams[1].handlers.onDone?.({ ...DONE, spots: [] });
      streams[1].end();
    });

    expect(tree.root.findAllByProps({ testID: "travel-anchor-row" })).toHaveLength(0);
  });

  it("카드 상세 탭은 스팟 상세로 간다", async () => {
    const { router } = jest.requireMock("expo-router") as { router: { push: jest.Mock } };
    const tree = await mount();
    await send(tree, "제주 계곡");
    await finishLast();

    await press(tree, "travel-card-126508");

    expect(router.push).toHaveBeenCalledWith("/spots/126508");
  });
});

describe("TravelScreen 실패와 재시도", () => {
  it("error 이벤트는 실패 문구와 사유, 다시 시도를 세운다", async () => {
    const tree = await mount();
    await send(tree, "제주 계곡");

    await act(async () => {
      streams[0].handlers.onError?.({ code: "AGENT_NO_RESULTS", message: "raw" });
      streams[0].end();
    });

    const out = rendered(tree);
    expect(out).toContain(FAIL_TITLE);
    expect(out).toContain("조건을 조금 넓혀서");
    expect(out).not.toContain("raw");
    expect(pressable(tree, "travel-retry")).toBeDefined();
  });

  it("다시 시도는 같은 입력을 다시 보내고 턴 수를 유지한다", async () => {
    const tree = await mount();
    await send(tree, "제주 계곡");
    await act(async () => {
      streams[0].handlers.onError?.({ code: "RATE_LIMITED", message: "" });
      streams[0].end();
    });

    await press(tree, "travel-retry");

    expect(streamChatMock).toHaveBeenCalledTimes(2);
    expect(streams[1].input.message).toBe("제주 계곡");
    expect(useChat.getState().turns).toHaveLength(1);
    expect(useChat.getState().turns[0].status).toBe("streaming");
  });

  it("done 없이 끝난 스트림은 실패 턴이 된다", async () => {
    const tree = await mount();
    await send(tree, "제주 계곡");

    await act(async () => streams[0].end());

    expect(useChat.getState().turns[0].status).toBe("error");
    expect(rendered(tree)).toContain(FAIL_TITLE);
  });
});

describe("TravelScreen 새 대화", () => {
  it("새 대화 버튼은 트랜스크립트를 비운다", async () => {
    const tree = await mount();
    await send(tree, "제주 계곡");
    await finishLast();
    expect(useChat.getState().turns).toHaveLength(1);

    await press(tree, "travel-new-chat");

    expect(useChat.getState().turns).toHaveLength(0);
    expect(rendered(tree)).not.toContain("제주 계곡");
  });

  it("새 대화 버튼에 접근성 라벨이 있다", async () => {
    const tree = await mount();

    expect(pressable(tree, "travel-new-chat")?.props.accessibilityLabel).toBe(NEW_CHAT_LABEL);
  });
});

describe("TravelScreen 사진 첨부", () => {
  function chooseAttach(index: number) {
    jest
      .spyOn(ActionSheetIOS, "showActionSheetWithOptions")
      .mockImplementation((_options, handler) => handler(index));
  }

  it("사진만 보내면 message 없이 photo가 나가고 말풍선은 대표 질문을 쓴다", async () => {
    pickTravelPhoto.mockResolvedValueOnce(PHOTO);
    chooseAttach(1);
    const tree = await mount();

    await press(tree, "travel-attach");
    expect(tree.root.findAllByProps({ testID: "travel-attach-banner" }).length).toBeGreaterThan(0);

    await press(tree, "travel-send");

    expect(streams[0].input.message).toBeNull();
    expect(streams[0].input.photo).toEqual(PHOTO);
    expect(useChat.getState().turns[0].question).toBe(PHOTO_ONLY_QUESTION);
    expect(useChat.getState().turns[0].photoUri).toBe(PHOTO.uri);
  });

  it("텍스트와 사진을 함께 보내면 둘 다 나간다", async () => {
    pickTravelPhoto.mockResolvedValueOnce(PHOTO);
    chooseAttach(1);
    const tree = await mount();
    await type(tree, "이런 분위기 어디");

    await press(tree, "travel-attach");
    await press(tree, "travel-send");

    expect(streams[0].input.message).toBe("이런 분위기 어디");
    expect(streams[0].input.photo).toEqual(PHOTO);
  });
});

describe("TravelScreen 초점 카드", () => {
  async function focusSecondCard(tree: renderer.ReactTestRenderer) {
    const carousel = tree.root.findByType(SpotCarousel);
    await act(async () => carousel.props.onFocusChange(1));
  }

  it("초점 카드 이름이 입력창 위 알약과 플레이스홀더에 선다", async () => {
    const tree = await mount();
    await send(tree, "제주 계곡");
    await finishLast();

    expect(rendered(tree)).toContain("무릉계곡");
    expect(input(tree).props.placeholder).toBe("무릉계곡에 대해 물어보세요");

    await focusSecondCard(tree);

    expect(input(tree).props.placeholder).toBe("천지연에 대해 물어보세요");
  });

  it("초점을 풀면 일반 질문으로 돌아간다", async () => {
    const tree = await mount();
    await send(tree, "제주 계곡");
    await finishLast();

    await press(tree, "travel-subject-clear");

    expect(tree.root.findAllByProps({ testID: "travel-subject" })).toHaveLength(0);
    expect(input(tree).props.placeholder).toBe(ASK_PLACEHOLDER);
  });

  it("타이핑한 질문에는 초점 카드가 맥락으로 실린다", async () => {
    const tree = await mount();
    await send(tree, "제주 계곡");
    await finishLast();
    await focusSecondCard(tree);

    await send(tree, "여기 주차돼?");

    expect(streams[1].input.context?.focusContentId).toBe("126509");
    expect(streams[1].input.anchor).toBeNull();
  });

  it("앵커 칩은 그 카드를 향한 새 턴을 연다", async () => {
    const tree = await mount();
    await send(tree, "제주 계곡");
    await finishLast();
    await focusSecondCard(tree);

    await press(tree, "travel-anchor-food");

    expect(streams[1].input.anchor).toEqual({ contentId: "126509", action: "food" });
    expect(streams[1].input.message).toBeNull();
    expect(rendered(tree)).toContain("천지연 근처 맛집");
  });
});

describe("TravelScreen 국외 이전 동의", () => {
  beforeEach(() => storageMock.getAiTransferConsent.mockResolvedValue(false));
  afterEach(() => storageMock.getAiTransferConsent.mockResolvedValue(true));

  it("동의 전에는 질문을 보내지 않고 5개 고지 항목을 띄운다", async () => {
    const tree = await mount();

    await send(tree, "제주 조용한 바다");

    expect(streamChatMock).not.toHaveBeenCalled();
    const shown = rendered(tree);
    expect(shown).toContain("이전받는 자 · 국가");
    expect(shown).toContain("이전되는 항목");
    expect(shown).toContain("이전 시기 · 방법");
    expect(shown).toContain("이용 목적 · 보유 기간");
    expect(shown).toContain("DeepSeek");
  });

  it("동의하면 기억하고 보류한 질문을 그대로 보낸다", async () => {
    const tree = await mount();
    await send(tree, "제주 조용한 바다");

    await press(tree, "ai-transfer-agree");

    expect(storageMock.setAiTransferConsent).toHaveBeenCalledWith(true);
    expect(streamChatMock).toHaveBeenCalledTimes(1);
    expect((streamChatMock.mock.calls[0][0] as ChatInput).message).toBe("제주 조용한 바다");
  });

  it("거절하면 질문을 버리고 이유를 알린다", async () => {
    const tree = await mount();
    await send(tree, "제주 조용한 바다");

    await press(tree, "ai-transfer-decline");

    expect(streamChatMock).not.toHaveBeenCalled();
    expect(storageMock.setAiTransferConsent).not.toHaveBeenCalled();
    expect(rendered(tree)).toContain("동의하지 않아 질문을 보내지 않았어요");
  });

  it("사진만 보낼 때는 동의를 묻지 않는다", async () => {
    pickTravelPhoto.mockResolvedValueOnce(PHOTO);
    jest
      .spyOn(ActionSheetIOS, "showActionSheetWithOptions")
      .mockImplementation((_options, handler) => handler(1));
    const tree = await mount();

    await press(tree, "travel-attach");
    await press(tree, "travel-send");

    expect(streams[0].input.message).toBeNull();
    expect(rendered(tree)).not.toContain("이전받는 자 · 국가");
  });
});
