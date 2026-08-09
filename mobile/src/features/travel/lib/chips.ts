import type { AnchorAction, QueryIntent, RefinePatch } from "@/features/travel/api";

export type Chip =
  | { kind: "question"; label: string; question: string }
  | { kind: "refine"; label: string; patch: RefinePatch }
  | { kind: "anchor"; label: string; action: AnchorAction }
  | { kind: "intent"; label: string; intent: QueryIntent };

export const NEARBY_ATTRACTION_CHIP: Chip = {
  kind: "intent",
  label: "근처 볼거리",
  intent: { categoryKeywords: [], regionHints: [], nearMe: true },
};

export const IDLE_CHIPS: Chip[] = [
  { kind: "anchor", label: "근처 카페", action: "cafe" },
  { kind: "anchor", label: "근처 맛집", action: "food" },
  NEARBY_ATTRACTION_CHIP,
];

export function idleChips(): Chip[] {
  return IDLE_CHIPS;
}
