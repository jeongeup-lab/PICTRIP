import { postChatTurn } from "@/features/chat/api";
import { api } from "@/lib/api-client";

jest.mock("@/lib/api-client", () => ({ api: { post: jest.fn() } }));

describe("postChatTurn", () => {
  it("posts to /chat/turn with a 30s timeout", async () => {
    (api.post as jest.Mock).mockResolvedValue({ sessionId: "s1" });
    const res = await postChatTurn({ utterance: "강릉 카페" });
    expect(api.post).toHaveBeenCalledWith(
      "/chat/turn",
      { utterance: "강릉 카페" },
      { timeout: 30000 },
    );
    expect(res.sessionId).toBe("s1");
  });
});
