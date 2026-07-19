import { useChatStore } from "@/features/chat/stores/chat-store";
import { postChatTurn } from "@/features/chat/api";
import type { ChatTurnResponse } from "@/features/chat/types";

jest.mock("@/features/chat/api", () => ({ postChatTurn: jest.fn() }));

const turnRes = (over: Partial<ChatTurnResponse> = {}): ChatTurnResponse => ({
  sessionId: "s1",
  round: 2,
  phase: "refining",
  poolTotal: 3214,
  candidateCount: 23,
  conditions: [{ id: "region:51150", label: "강릉시", exclude: false }],
  botText: "23곳 남았어요.",
  cards: [
    {
      contentId: "c1",
      title: "안목해변 카페",
      firstImageUrl: "http://kto/i.jpg",
      category: "카페",
      regionLabel: "강원특별자치도 강릉시",
      why: "바다 정면",
      quiet: true,
    },
  ],
  question: "사람 붐비는 건 어떠세요?",
  answers: [{ id: "quiet:0", label: "한적한 곳이 좋아요", kind: "ask", utterance: "한적한" }],
  ...over,
});

beforeEach(() => {
  useChatStore.getState().reset();
  jest.clearAllMocks();
});

describe("chat-store", () => {
  it("send appends user + bot entries and tracks pool/candidate", async () => {
    (postChatTurn as jest.Mock).mockResolvedValue(turnRes());
    await useChatStore.getState().send("강릉 감성 카페");
    const s = useChatStore.getState();
    expect(s.entries.map((e) => e.role)).toEqual(["user", "bot"]);
    expect(s.sessionId).toBe("s1");
    expect(s.poolTotal).toBe(3214);
    expect(s.candidateCount).toBe(23);
    expect(s.entries[1].board?.question).toBe("사람 붐비는 건 어떠세요?");
  });

  it("subsequent turn sends the stored sessionId", async () => {
    (postChatTurn as jest.Mock).mockResolvedValue(turnRes());
    await useChatStore.getState().send("강릉");
    (postChatTurn as jest.Mock).mockResolvedValue(turnRes({ candidateCount: 14 }));
    await useChatStore.getState().pickAnswer({ id: "quiet:skip", label: "괜찮아요", kind: "skip" });
    expect(postChatTurn).toHaveBeenLastCalledWith({ sessionId: "s1", skip: true });
    expect(useChatStore.getState().candidateCount).toBe(14);
  });

  it("send failure appends a retryable error entry", async () => {
    (postChatTurn as jest.Mock).mockRejectedValue(new Error("boom"));
    await useChatStore.getState().send("강릉");
    const s = useChatStore.getState();
    expect(s.pending).toBe(false);
    expect(s.entries[s.entries.length - 1].text).toContain("다시");
  });

  it("commit appends a conclusion entry and switches phase to done", async () => {
    (postChatTurn as jest.Mock).mockResolvedValue(turnRes({ phase: "converged" }));
    await useChatStore.getState().send("강릉 카페");
    useChatStore.getState().commit();
    const s = useChatStore.getState();
    expect(s.phase).toBe("done");
    const last = s.entries[s.entries.length - 1];
    expect(last.role).toBe("conclusion");
    expect(last.conclusion?.spots).toHaveLength(1);
    expect(last.conclusion?.summary).toContain("강릉시");
  });

  it("restart answer resets the store", async () => {
    (postChatTurn as jest.Mock).mockResolvedValue(turnRes());
    await useChatStore.getState().send("강릉");
    await useChatStore
      .getState()
      .pickAnswer({ id: "restart", label: "다른 결로 다시", kind: "restart" });
    expect(useChatStore.getState().entries).toHaveLength(0);
    expect(useChatStore.getState().sessionId).toBeNull();
  });
});
