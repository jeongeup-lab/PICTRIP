import type { SpotCard } from "@/lib/api-types";

export const RECENT_SPOTS_LIMIT = 8;

export function pushRecent(
  list: readonly SpotCard[],
  spot: SpotCard,
  limit: number = RECENT_SPOTS_LIMIT,
): SpotCard[] {
  const rest = list.filter((s) => s.contentId !== spot.contentId);
  return [spot, ...rest].slice(0, limit);
}
