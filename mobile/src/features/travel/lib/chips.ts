import type {
  AgentAnswer,
  AnchorAction,
  QueryIntent,
  RefinePatch,
  Suggestion,
} from "@/features/travel/api";

export type Chip =
  | { kind: "question"; label: string; question: string }
  | { kind: "refine"; label: string; patch: RefinePatch }
  | { kind: "anchor"; label: string; action: AnchorAction }
  | { kind: "intent"; label: string; intent: QueryIntent };

export type AnchorChip = Extract<Chip, { kind: "anchor" }>;

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

const CONTEXT_PREDICATES: { suffix: string; action: AnchorAction }[] = [
  { suffix: "근처 카페", action: "cafe" },
  { suffix: "근처 맛집", action: "food" },
  { suffix: "근처 볼거리", action: "nearby" },
];

const CROWD_PREDICATE = "오늘 붐벼?";

export function contextChips(title: string, hasCrowd: boolean): AnchorChip[] {
  const near = CONTEXT_PREDICATES.map(({ suffix, action }) => ({
    kind: "anchor" as const,
    label: `${title} ${suffix}`,
    action,
  }));
  if (!hasCrowd) return near;
  return [...near, { kind: "anchor", label: `${title} ${CROWD_PREDICATE}`, action: "crowd" }];
}

export function refineChips(refinements: Suggestion[] | null | undefined): Chip[] {
  return (refinements ?? []).map((s) => ({ kind: "refine", label: s.label, patch: s.patch }));
}

export type ChipAnswer = Pick<AgentAnswer, "totalCount" | "refinements"> & {
  intent?: QueryIntent | null;
};
