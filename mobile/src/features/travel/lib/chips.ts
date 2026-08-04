import type { AnchorAction, RefinePatch, Suggestion } from "@/features/travel/api";

export type Chip =
  | { kind: "question"; label: string; question: string }
  | { kind: "refine"; label: string; patch: RefinePatch }
  | { kind: "anchor"; label: string; action: AnchorAction };

export type AnchorChip = Extract<Chip, { kind: "anchor" }>;

export const ANCHOR_CHIPS: AnchorChip[] = [
  { kind: "anchor", label: "근처 맛집", action: "food" },
  { kind: "anchor", label: "근처 카페", action: "cafe" },
  { kind: "anchor", label: "주변 볼거리", action: "nearby" },
  { kind: "anchor", label: "오늘 붐벼?", action: "crowd" },
];

export function anchorChips(hasCrowd: boolean): Chip[] {
  return hasCrowd ? ANCHOR_CHIPS : ANCHOR_CHIPS.filter((chip) => chip.action !== "crowd");
}

export type QuestionChip = Extract<Chip, { kind: "question" }>;

export const NEARBY_CHIP: QuestionChip = {
  kind: "question",
  label: "내 근처",
  question: "여기서 가까운 곳",
};

const BASE_CHIPS: Chip[] = [
  { kind: "question", label: "지금 열리는 축제", question: "지금 열리는 축제" },
  { kind: "question", label: "사람 적은 바닷가", question: "사람 적은 바닷가" },
  { kind: "question", label: "비 와도 갈 만한 실내", question: "비 와도 갈 만한 실내" },
  { kind: "question", label: "제주에서 한적한 곳", question: "제주에서 한적한 곳" },
];

export function idleChips(): Chip[] {
  return [...BASE_CHIPS];
}

export function refineChips(refinements: Suggestion[] | null | undefined): Chip[] {
  return (refinements ?? []).map((s) => ({ kind: "refine", label: s.label, patch: s.patch }));
}

export function composerChips(
  refinements: Suggestion[] | null | undefined,
  anchor: { hasCrowd?: boolean } | null = null,
): Chip[] {
  if (anchor) return anchorChips(anchor.hasCrowd === true);
  const refine = refineChips(refinements);
  return refine.length > 0 ? refine : idleChips();
}
