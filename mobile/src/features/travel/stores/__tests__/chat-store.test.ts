import {
  HISTORY_LIMIT,
  HISTORY_TEXT_LIMIT,
  historyOf,
  lastDoneTurn,
  useChat,
  type ChatRequestSeed,
  type ChatTurn,
} from "@/features/travel/stores/chat-store";
import type { ChatDoneEvent, TravelSpot } from "@/features/travel/api";

const seed: ChatRequestSeed = {
  message: "정읍 맛집",
  photo: null,
  context: null,
  intent: null,
  patch: null,
  anchor: null,
  history: [],
};

const spot = (id: string): TravelSpot => ({
  contentId: id,
  title: `spot-${id}`,
  regionLabel: "전북 정읍시",
  imageUrl: null,
  tag: null,
  lat: null,
  lng: null,
});

const doneEvent = (over: Partial<ChatDoneEvent> = {}): ChatDoneEvent => ({
  answerText: "정읍이라면 **쌍화차 거리**가 유명해요.",
  spots: [spot("1")],
  sources: [{ kind: "naver_blog", title: "정읍 카페 후기", url: "https://blog", date: "20260801" }],
  intent: { categoryKeywords: ["맛집"], regionHints: ["정읍"] },
  totalCount: 4,
  ...over,
});

function begin(id = "turn-1", question = "정읍 맛집") {
  useChat.getState().begin({ id, question, photoUri: null, request: seed });
}

beforeEach(() => {
  useChat.setState({ turns: [], streaming: false, activeId: null, issued: 0 });
});

describe("chat-store 스트리밍", () => {
  it("begin은 스트리밍 턴을 추가하고 입력을 잠근다", () => {
    begin();

    const state = useChat.getState();
    expect(state.streaming).toBe(true);
    expect(state.turns).toHaveLength(1);
    expect(state.turns[0].status).toBe("streaming");
    expect(state.turns[0].question).toBe("정읍 맛집");
  });

  it("delta가 순서대로 본문에 쌓인다", () => {
    begin();
    useChat.getState().appendDelta("turn-1", "정읍이라면 ");
    useChat.getState().appendDelta("turn-1", "쌍화차 거리요.");

    expect(useChat.getState().turns[0].text).toBe("정읍이라면 쌍화차 거리요.");
  });

  it("같은 index의 step은 run에서 done으로 교체된다", () => {
    begin();
    useChat.getState().applyStep("turn-1", { index: 0, label: "조건 읽는 중", status: "run" });
    useChat
      .getState()
      .applyStep("turn-1", { index: 0, label: "조건 읽는 중", badge: "맛집", status: "done" });
    useChat.getState().applyStep("turn-1", { index: 1, label: "후보 찾는 중", status: "run" });

    const steps = useChat.getState().turns[0].steps;
    expect(steps).toHaveLength(2);
    expect(steps[0]).toEqual({ index: 0, label: "조건 읽는 중", badge: "맛집", status: "done" });
    expect(steps[1].status).toBe("run");
  });

  it("cards와 sources가 턴에 붙는다", () => {
    begin();
    useChat
      .getState()
      .setCards("turn-1", { spots: [spot("1"), spot("2")], tagBasis: "한적함 기준" });
    useChat.getState().setSources("turn-1", [{ kind: "kto", title: "관광정보" }]);

    const turn = useChat.getState().turns[0];
    expect(turn.spots.map((s) => s.contentId)).toEqual(["1", "2"]);
    expect(turn.tagBasis).toBe("한적함 기준");
    expect(turn.sources[0].kind).toBe("kto");
  });

  it("done은 조립본으로 턴을 확정하고 잠금을 푼다", () => {
    begin();
    useChat.getState().appendDelta("turn-1", "부분 텍스트");
    useChat.getState().applyStep("turn-1", { index: 0, label: "조회", status: "run" });
    useChat.getState().finish("turn-1", doneEvent());

    const state = useChat.getState();
    expect(state.streaming).toBe(false);
    expect(state.turns[0].status).toBe("done");
    expect(state.turns[0].text).toBe("정읍이라면 **쌍화차 거리**가 유명해요.");
    expect(state.turns[0].steps[0].status).toBe("done");
    expect(state.turns[0].intent?.regionHints).toEqual(["정읍"]);
  });

  it("활성 턴이 아니면 늦게 온 이벤트를 버린다", () => {
    begin();
    useChat.getState().fail("turn-1", "AGENT_NO_RESULTS");
    useChat.getState().appendDelta("turn-1", "늦은 델타");
    useChat.getState().finish("turn-1", doneEvent());

    const turn = useChat.getState().turns[0];
    expect(turn.status).toBe("error");
    expect(turn.text).toBe("");
  });

  it("fail은 errorCode를 남긴다", () => {
    begin();
    useChat.getState().fail("turn-1", "RATE_LIMITED");

    const state = useChat.getState();
    expect(state.streaming).toBe(false);
    expect(state.turns[0].status).toBe("error");
    expect(state.turns[0].errorCode).toBe("RATE_LIMITED");
  });
});

describe("chat-store 재시도", () => {
  it("실패 턴을 제자리에서 비우고 턴 수를 유지한다", () => {
    begin("turn-1");
    useChat.getState().appendDelta("turn-1", "부분");
    useChat.getState().fail("turn-1", "NETWORK_ERROR");

    useChat.getState().retry("turn-1", seed);

    const state = useChat.getState();
    expect(state.turns).toHaveLength(1);
    expect(state.streaming).toBe(true);
    expect(state.activeId).toBe("turn-1");
    const turn = state.turns[0];
    expect(turn.status).toBe("streaming");
    expect(turn.text).toBe("");
    expect(turn.steps).toEqual([]);
    expect(turn.errorCode).toBeNull();
    expect(turn.question).toBe("정읍 맛집");
    expect(turn.request).toEqual(seed);
  });

  it("재시도 시드로 이력을 갈아끼운다", () => {
    begin("turn-1");
    useChat.getState().fail("turn-1", "VALIDATION_FAILED");

    const rebuilt: ChatRequestSeed = { ...seed, history: [{ role: "user", text: "이전" }] };
    useChat.getState().retry("turn-1", rebuilt);

    expect(useChat.getState().turns[0].request).toEqual(rebuilt);
  });
});

describe("historyOf", () => {
  const doneTurn = (id: string, text: string, spots: TravelSpot[] = []): ChatTurn => ({
    id,
    question: `질문-${id}`,
    photoUri: null,
    request: seed,
    status: "done",
    steps: [],
    text,
    spots,
    tagBasis: null,
    refinements: [],
    sources: [],
    intent: null,
    errorCode: null,
  });

  it("user와 assistant를 짝지어 만든다", () => {
    const items = historyOf([doneTurn("a", "답변", [spot("126508")])]);

    expect(items).toEqual([
      { role: "user", text: "질문-a" },
      { role: "assistant", text: "답변", spotIds: ["126508"] },
    ]);
  });

  it("assistant 텍스트는 앞 300자만 담는다", () => {
    const long = "가".repeat(400);
    const items = historyOf([doneTurn("a", long)]);

    expect(items[1].text).toHaveLength(HISTORY_TEXT_LIMIT);
  });

  it("실패 턴은 user 항목만 남긴다", () => {
    const failed: ChatTurn = { ...doneTurn("a", ""), status: "error", errorCode: "UNKNOWN" };
    const items = historyOf([failed]);

    expect(items).toEqual([{ role: "user", text: "질문-a" }]);
  });

  it("최근 8개 항목만 남긴다", () => {
    const turns = ["a", "b", "c", "d", "e", "f"].map((id) => doneTurn(id, `답-${id}`));
    const items = historyOf(turns);

    expect(items).toHaveLength(HISTORY_LIMIT);
    expect(items[0]).toEqual({ role: "user", text: "질문-c" });
    expect(items[items.length - 1]).toEqual({ role: "assistant", text: "답-f", spotIds: [] });
  });
});

describe("lastDoneTurn", () => {
  it("마지막 done 턴을 찾고 없으면 null", () => {
    const done: ChatTurn = {
      id: "a",
      question: "q",
      photoUri: null,
      request: seed,
      status: "done",
      steps: [],
      text: "",
      spots: [],
      tagBasis: null,
      refinements: [],
      sources: [],
      intent: null,
      errorCode: null,
    };
    const failed: ChatTurn = { ...done, id: "b", status: "error" };

    expect(lastDoneTurn([done, failed])?.id).toBe("a");
    expect(lastDoneTurn([failed])).toBeNull();
    expect(lastDoneTurn([])).toBeNull();
  });
});
