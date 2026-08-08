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

export const ANCHOR_CHIPS: AnchorChip[] = [
  { kind: "anchor", label: "맛집", action: "food" },
  { kind: "anchor", label: "카페", action: "cafe" },
  { kind: "anchor", label: "볼거리", action: "nearby" },
  { kind: "anchor", label: "오늘 붐벼?", action: "crowd" },
];

export function anchorChips(hasCrowd: boolean): Chip[] {
  return hasCrowd ? ANCHOR_CHIPS : ANCHOR_CHIPS.filter((chip) => chip.action !== "crowd");
}

export const FESTIVAL_CHIP: Chip = {
  kind: "intent",
  label: "지금 축제",
  intent: { categoryKeywords: [], regionHints: [], festivalOnly: true },
};

export const NEARBY_ATTRACTION_CHIP: Chip = {
  kind: "intent",
  label: "근처 볼거리",
  intent: { categoryKeywords: [], regionHints: [], nearMe: true },
};

const NEARBY_IDLE_CHIPS: Chip[] = [
  { kind: "anchor", label: "근처 맛집", action: "food" },
  NEARBY_ATTRACTION_CHIP,
  { kind: "anchor", label: "근처 카페", action: "cafe" },
];

const BASE_CHIPS: Chip[] = [
  FESTIVAL_CHIP,
  { kind: "question", label: "사람 적은 바닷가", question: "사람 적은 바닷가" },
  { kind: "question", label: "비 와도 갈 만한 실내", question: "비 와도 갈 만한 실내" },
  { kind: "question", label: "제주에서 한적한 곳", question: "제주에서 한적한 곳" },
];

export function idleChips(hasCoords: boolean = false): Chip[] {
  return hasCoords ? [...NEARBY_IDLE_CHIPS, FESTIVAL_CHIP] : [...BASE_CHIPS];
}

export function refineChips(refinements: Suggestion[] | null | undefined): Chip[] {
  return (refinements ?? []).map((s) => ({ kind: "refine", label: s.label, patch: s.patch }));
}

export type ChipAnswer = Pick<AgentAnswer, "totalCount" | "refinements"> & {
  intent?: QueryIntent | null;
};
