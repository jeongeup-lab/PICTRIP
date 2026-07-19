import { api } from "@/lib/api-client";
import type { ChatTurnBody, ChatTurnResponse } from "@/features/chat/types";

/** One conversation turn. LLM round-trip can be slow, so a wider timeout than default. */
export async function postChatTurn(body: ChatTurnBody): Promise<ChatTurnResponse> {
  return (await api.post("/chat/turn", body, { timeout: 30000 })) as unknown as ChatTurnResponse;
}

export interface MoodCover {
  utterance: string;
  coverUrl: string | null;
}

/** Representative cover image per mood utterance — the first candidate a tap would surface. */
export async function fetchMoodCovers(utterances: string[]): Promise<MoodCover[]> {
  const res = (await api.post("/chat/mood-covers", { utterances })) as unknown as {
    covers: MoodCover[];
  };
  return res.covers;
}
