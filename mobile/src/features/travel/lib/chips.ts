import type { AnchorAction, QueryIntent } from "@/features/travel/api";

export type Chip =
  | { kind: "anchor"; label: string; action: AnchorAction }
  | { kind: "intent"; label: string; intent: QueryIntent };

export const NEARBY_ATTRACTION_CHIP: Chip = {
  kind: "intent",
  label: "근처 볼거리",
  intent: { categoryKeywords: [], regionHints: [], nearMe: true },
};

export const QUIET_NATURE_CHIP: Chip = {
  kind: "intent",
  label: "한적한 자연",
  intent: { categoryKeywords: ["자연"], regionHints: [], crowdPreference: "quiet" },
};

export const INDOOR_OUTING_CHIP: Chip = {
  kind: "intent",
  label: "실내 나들이",
  intent: { categoryKeywords: [], regionHints: [], indoorOnly: true },
};

export const IDLE_CHIPS: Chip[] = [
  { kind: "anchor", label: "근처 카페", action: "cafe" },
  { kind: "anchor", label: "근처 맛집", action: "food" },
  NEARBY_ATTRACTION_CHIP,
  QUIET_NATURE_CHIP,
  INDOOR_OUTING_CHIP,
];

export function idleChips(): Chip[] {
  return IDLE_CHIPS;
}
