import type { AskContext, AgentAnswer } from "@/features/travel/api";

export const MAX_CONTEXT_SPOTS = 8;

export function contextFrom(answer: AgentAnswer | null | undefined): AskContext | null {
  if (!answer) return null;
  const spots = answer.spots.slice(0, MAX_CONTEXT_SPOTS).map((spot) => ({
    contentId: spot.contentId,
    title: spot.title,
  }));
  if (spots.length === 0 && !answer.intent) return null;
  return { intent: answer.intent ?? null, spots };
}
