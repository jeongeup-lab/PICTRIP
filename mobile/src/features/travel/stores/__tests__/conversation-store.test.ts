import type { AgentAnswer } from "@/features/travel/api";
import { useConversation } from "@/features/travel/stores/conversation-store";

const answer: AgentAnswer = {
  steps: [{ tool: "intent", label: "질문에서 조건 추출", badge: "96곳" }],
  answer: [{ text: "4곳 찾았어요", emphasis: false }],
  spots: [],
  totalCount: 4,
  intent: { categoryKeywords: ["계곡"], regionHints: [] },
  suggestions: ["더 가까운 곳"],
  refinements: [{ label: "더 가까운 곳", patch: { nearMe: true } }],
};

beforeEach(() => useConversation.getState().clear());

describe("conversation store", () => {
  it("releases the dock the moment the response lands", () => {
    useConversation.getState().start({ id: "t1", question: "계곡", request: "계곡", photo: null });
    expect(useConversation.getState().busy).toBe(true);

    useConversation.getState().resolve("t1", answer);
    expect(useConversation.getState().busy).toBe(false);
    expect(useConversation.getState().turns[0].status).toBe("done");
  });

  it("ignores a response that lands after the conversation was cleared", () => {
    useConversation.getState().start({ id: "t1", question: "계곡", request: "계곡", photo: null });
    useConversation.getState().clear();
    useConversation.getState().start({ id: "t2", question: "바다", request: "바다", photo: null });

    useConversation.getState().resolve("t1", answer);

    expect(useConversation.getState().busy).toBe(true);
    expect(useConversation.getState().turns).toHaveLength(1);
    expect(useConversation.getState().turns[0].status).toBe("pending");
  });

  it("ignores a late failure from a turn the user already walked away from", () => {
    useConversation.getState().start({ id: "t1", question: "계곡", request: "계곡", photo: null });
    useConversation.getState().clear();
    useConversation.getState().start({ id: "t2", question: "바다", request: "바다", photo: null });

    useConversation.getState().fail("t1", "실패");

    expect(useConversation.getState().busy).toBe(true);
    expect(useConversation.getState().turns[0].errorMessage).toBeNull();
  });

  it("releases the dock immediately on failure so the retry chip works", () => {
    useConversation.getState().start({ id: "t1", question: "계곡", request: "계곡", photo: null });
    useConversation.getState().fail("t1", "답을 만들지 못했어요.");
    const turn = useConversation.getState().turns[0];
    expect(useConversation.getState().busy).toBe(false);
    expect(turn.status).toBe("failed");
    expect(turn.errorMessage).toBe("답을 만들지 못했어요.");
  });

  it("retries in place instead of appending a second turn", () => {
    useConversation.getState().start({ id: "t1", question: "계곡", request: "계곡", photo: null });
    useConversation.getState().fail("t1", "실패");
    useConversation.getState().retry("t1");
    expect(useConversation.getState().turns).toHaveLength(1);
    expect(useConversation.getState().turns[0].status).toBe("pending");
    expect(useConversation.getState().turns[0].errorMessage).toBeNull();
  });

  it("keeps the picked photo on the turn so a retry can resend it", () => {
    const photo = { uri: "file:///a.jpg", name: "a.jpg", type: "image/jpeg" };
    useConversation.getState().start({ id: "t1", question: "이 사진", request: "이 사진", photo });
    expect(useConversation.getState().turns[0].photo).toEqual(photo);
  });

  it("keeps intent and patch on the turn so a retry resends the refine, not the label", () => {
    const intent = { categoryKeywords: ["계곡"], regionHints: [], crowdPreference: "any" as const };
    const patch = { indoorOnly: true };
    useConversation.getState().start({
      id: "t1",
      question: "실내만",
      request: "",
      photo: null,
      intent,
      patch,
    });
    const turn = useConversation.getState().turns[0];
    expect(turn.intent).toEqual(intent);
    expect(turn.patch).toEqual({ indoorOnly: true });
    expect(turn.request).toBe("");
  });

  it("leaves intent and patch null for a plain typed question", () => {
    useConversation.getState().start({ id: "t1", question: "계곡", request: "계곡", photo: null });
    const turn = useConversation.getState().turns[0];
    expect(turn.intent).toBeNull();
    expect(turn.patch).toBeNull();
  });

  it("appends turns in ask order", () => {
    useConversation
      .getState()
      .start({ id: "t1", question: "첫 질문", request: "첫 질문", photo: null });
    useConversation.getState().resolve("t1", answer);
    useConversation
      .getState()
      .start({ id: "t2", question: "둘째 질문", request: "둘째 질문", photo: null });
    expect(useConversation.getState().turns.map((t) => t.question)).toEqual([
      "첫 질문",
      "둘째 질문",
    ]);
  });
});

describe("turn ids", () => {
  it("hands out a fresh id every call, not one derived from the turns it can see", () => {
    const issued = [
      useConversation.getState().nextTurnId(),
      useConversation.getState().nextTurnId(),
      useConversation.getState().nextTurnId(),
    ];

    expect(new Set(issued).size).toBe(3);
  });

  it("keeps counting past the turns already in the conversation", () => {
    const first = useConversation.getState().nextTurnId();
    useConversation.getState().start({
      id: first,
      question: "사람 적은 바닷가",
      request: "사람 적은 바닷가",
      photo: null,
    });

    expect(useConversation.getState().nextTurnId()).not.toBe(first);
    expect(useConversation.getState().turns.map((t) => t.id)).toEqual([first]);
  });

  it("keeps counting across a cleared conversation so a late reply cannot land on a new turn", () => {
    const before = useConversation.getState().nextTurnId();
    useConversation.getState().start({
      id: before,
      question: "사람 적은 바닷가",
      request: "사람 적은 바닷가",
      photo: null,
    });

    useConversation.getState().clear();

    expect(useConversation.getState().nextTurnId()).not.toBe(before);
  });
});
