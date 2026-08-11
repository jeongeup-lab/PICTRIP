import { formatDistance } from "@/lib/distance";
import type { HomeSpotCard } from "@/features/home/api";

export function distanceSubtitle(card: HomeSpotCard): string {
  return card.dist === null ? card.regionLabel : `여기서 ${formatDistance(card.dist)}`;
}

const DAY_TRIP_M = 30_000;

export function categorySubtitle(card: HomeSpotCard): string {
  const place =
    card.dist !== null && card.dist < DAY_TRIP_M ? formatDistance(card.dist) : card.regionLabel;
  return [card.category, place].filter(Boolean).join(" · ");
}

export function anchorBadge(card: HomeSpotCard): string | null {
  return card.anchorTitle ? `저장한 ${card.anchorTitle}과 비슷한` : null;
}
