import type { AnchorAction, Suggestion } from "@/features/travel/api";
import type { FollowKey, Turn } from "@/features/travel/stores/conversation-store";

export type FollowAction =
  | { kind: "anchor"; action: AnchorAction; question: string }
  | { kind: "detail"; followKey: FollowKey; question: string }
  | { kind: "refine"; label: string; patch: Suggestion["patch"] }
  | { kind: "question"; question: string };

export interface FollowChip {
  label: string;
  action: FollowAction;
}

export interface FollowUpBlock {
  line: string;
  chips: FollowChip[];
}

export const MAX_FOLLOW_CHIPS = 3;
export const SEARCH_LINE = "결과를 더 좁혀볼까요?";
export const DETAIL_LINE = "여기서 더 찾아볼까요?";
export const ABOUT_LABEL = "여긴 어떤 곳이야?";
export const RELATED_LABEL = "연관 관광지는?";
export const NEAR_FOOD_LABEL = "근처 맛집";

export function askedKeys(turns: Turn[]): Set<string> {
  const keys = new Set<string>();
  for (const turn of turns) {
    if (turn.anchor?.contentId) {
      keys.add(`anchor:${turn.anchor.action}:${turn.anchor.contentId}`);
    }
    if (turn.followKey) {
      keys.add(`detail:${turn.followKey}:${turn.context?.focusContentId ?? ""}`);
    }
    if (turn.request) {
      keys.add(`q:${turn.request}`);
    }
  }
  return keys;
}

interface FollowUpInput {
  title: string;
  contentId: string | null;
  asked: ReadonlySet<string>;
  isDetailTurn: boolean;
  refinements: Suggestion[] | null;
  suggestions: string[] | null;
}

function aboutChip(input: FollowUpInput): FollowChip | null {
  const id = input.contentId;
  if (id === null || input.asked.has(`detail:about:${id}`)) return null;
  return {
    label: ABOUT_LABEL,
    action: { kind: "detail", followKey: "about", question: `${input.title}은 어떤 곳이야?` },
  };
}

function relatedChip(input: FollowUpInput): FollowChip | null {
  const id = input.contentId;
  if (id === null || input.asked.has(`anchor:related:${id}`)) return null;
  return {
    label: RELATED_LABEL,
    action: { kind: "anchor", action: "related", question: `${input.title} 연관 관광지는?` },
  };
}

function nearFoodChip(input: FollowUpInput): FollowChip | null {
  const id = input.contentId;
  if (id === null || input.asked.has(`anchor:food:${id}`)) return null;
  return {
    label: NEAR_FOOD_LABEL,
    action: { kind: "anchor", action: "food", question: `${input.title} 근처 맛집` },
  };
}

function refineChips(input: FollowUpInput): FollowChip[] {
  return (input.refinements ?? []).map((r) => ({
    label: r.label,
    action: { kind: "refine", label: r.label, patch: r.patch },
  }));
}

function suggestionChips(input: FollowUpInput, shown: ReadonlySet<string>): FollowChip[] {
  const chips: FollowChip[] = [];
  for (const q of input.suggestions ?? []) {
    if (shown.has(q) || input.asked.has(`q:${q}`)) continue;
    chips.push({ label: q, action: { kind: "question", question: q } });
  }
  return chips;
}

function compact(chips: (FollowChip | null)[]): FollowChip[] {
  return chips.filter((chip): chip is FollowChip => chip !== null);
}

export function followUps(input: FollowUpInput): FollowUpBlock {
  const chips = input.isDetailTurn
    ? compact([relatedChip(input), nearFoodChip(input), ...refineChips(input)])
    : compact([...refineChips(input), aboutChip(input)]);
  const shown = new Set(chips.map((chip) => chip.label));
  const line = input.isDetailTurn ? DETAIL_LINE : SEARCH_LINE;
  return { line, chips: [...chips, ...suggestionChips(input, shown)].slice(0, MAX_FOLLOW_CHIPS) };
}
