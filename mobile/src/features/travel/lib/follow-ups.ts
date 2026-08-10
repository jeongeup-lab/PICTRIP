import type { AnchorAction, Suggestion } from "@/features/travel/api";
import type { FollowKey, Turn } from "@/features/travel/stores/conversation-store";
import { NEAR_CHIPS } from "@/features/travel/lib/starter-chips";

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

export const MAX_FOLLOW_CHIPS = 5;
export const MAX_REFINE_CHIPS = 2;
export const FOLLOW_LINE = "이 근처를 더 볼까요?";

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

function refineChips(input: FollowUpInput): FollowChip[] {
  return (input.refinements ?? []).slice(0, MAX_REFINE_CHIPS).map((r) => ({
    label: r.label,
    action: { kind: "refine" as const, label: r.label, patch: r.patch },
  }));
}

export function followUps(input: FollowUpInput): FollowUpBlock {
  const id = input.contentId ?? "";
  const near: FollowChip[] = NEAR_CHIPS.filter(
    (chip) => !input.asked.has(`anchor:${chip.action}:${id}`),
  ).map((chip) => ({
    label: chip.label,
    action: {
      kind: "anchor" as const,
      action: chip.action,
      question: `${input.title} ${chip.label}`,
    },
  }));
  const chips = [...near, ...refineChips(input)];
  return { line: FOLLOW_LINE, chips: chips.slice(0, MAX_FOLLOW_CHIPS) };
}
