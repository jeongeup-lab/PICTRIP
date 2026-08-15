import type { AskContext, QueryIntent } from "@/features/travel/api";

export const MAX_CONTEXT_SPOTS = 8;

export interface ContextSource {
  intent?: QueryIntent | null;
  spots: { contentId: string; title: string }[];
}

export function contextFrom(
  source: ContextSource | null | undefined,
  focusContentId: string | null = null,
): AskContext | null {
  const focus = focusContentId ?? undefined;
  if (!source) return focus ? { spots: [], focusContentId: focus } : null;
  const spots = source.spots.slice(0, MAX_CONTEXT_SPOTS).map((spot) => ({
    contentId: spot.contentId,
    title: spot.title,
  }));
  if (spots.length === 0 && !source.intent && !focus) return null;
  return { intent: source.intent ?? null, spots, focusContentId: focus };
}
