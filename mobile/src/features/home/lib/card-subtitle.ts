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

const HANGUL_BASE = 0xac00;
const HANGUL_LAST = 0xd7a3;
const JONGSEONG_COUNT = 28;
const CODA_DIGITS = new Set(["0", "1", "3", "6", "7", "8"]);

export function withParticle(word: string, withCoda: string, withoutCoda: string): string {
  const last = word.trim().slice(-1);
  if (!last) return withoutCoda;
  const code = last.charCodeAt(0);
  if (code >= HANGUL_BASE && code <= HANGUL_LAST) {
    return (code - HANGUL_BASE) % JONGSEONG_COUNT === 0 ? withoutCoda : withCoda;
  }
  if (last >= "0" && last <= "9") return CODA_DIGITS.has(last) ? withCoda : withoutCoda;
  return withoutCoda;
}

const ANCHOR_MAX = 12;

export function anchorBadge(card: HomeSpotCard): string | null {
  const anchor = card.anchorTitle?.trim();
  if (!anchor) return null;
  const clipped = anchor.length > ANCHOR_MAX ? `${anchor.slice(0, ANCHOR_MAX)}…` : anchor;
  return `저장한 ${clipped}${withParticle(clipped, "과", "와")} 비슷한 곳`;
}
