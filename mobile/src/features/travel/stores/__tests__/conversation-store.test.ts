import type { AgentAnswer } from "@/features/travel/api";
import { useConversation } from "@/features/travel/stores/conversation-store";

const answer: AgentAnswer = {
  steps: [{ tool: "intent", label: "질문에서 조건 추출", badge: "96곳" }],
  answer: [{ text: "4곳 찾았어요", emphasis: false }],
  spots: [],
  totalCount: 4,
  intent: { categoryKeywords: ["계곡"], regionHints: [] },
  suggestions: [{ label: "더 가까운 곳", patch: { nearMe: true } }],
};

beforeEach(() => useConversation.getState().clear());

describe("conversation store", () => {
  it("stays busy from the ask until playback ends, not until the response lands", () => {
    useConversation.getState().start({ id: "t1", question: "계곡", request: "계곡", photo: null });
    expect(useConversation.getState().busy).toBe(true);

    useConversation.getState().resolve("t1", answer);
    expect(useConversation.getState().busy).toBe(true);
    expect(useConversation.getState().turns[0].status).toBe("playing");

    useConversation.getState().finishPlayback("t1");
    expect(useConversation.getState().busy).toBe(false);
    expect(useConversation.getState().turns[0].status).toBe("done");
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

  it("appends turns in ask order", () => {
    useConversation
      .getState()
      .start({ id: "t1", question: "첫 질문", request: "첫 질문", photo: null });
    useConversation.getState().finishPlayback("t1");
    useConversation
      .getState()
      .start({ id: "t2", question: "둘째 질문", request: "둘째 질문", photo: null });
    expect(useConversation.getState().turns.map((t) => t.question)).toEqual([
      "첫 질문",
      "둘째 질문",
    ]);
  });
});
