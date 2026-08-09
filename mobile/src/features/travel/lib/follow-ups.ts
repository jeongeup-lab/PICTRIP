import type { AnchorAction, Suggestion } from "@/features/travel/api";
import type { FollowKey, Turn } from "@/features/travel/stores/conversation-store";

export type FollowBranch = "root" | "near";

export type FollowAction =
  | { kind: "branch"; to: FollowBranch }
  | { kind: "anchor"; action: AnchorAction; question: string }
  | { kind: "detail"; followKey: FollowKey; question: string }
  | { kind: "refine"; label: string; patch: Suggestion["patch"] }
  | { kind: "question"; question: string };

export interface FollowChip {
  label: string;
  action: FollowAction;
  muted?: boolean;
}

export interface FollowUpBlock {
  line: string;
  chips: FollowChip[];
}

export const MAX_FOLLOW_CHIPS = 5;

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
  categoryGroup: string | null;
  hasCrowd: boolean;
  branch: FollowBranch;
  asked: ReadonlySet<string>;
  isDetailTurn: boolean;
  refinements: Suggestion[] | null;
  suggestions: string[] | null;
}

const NEAR_OPTIONS: { action: AnchorAction; label: string; excludeGroup: string | null }[] = [
  { action: "cafe", label: "카페", excludeGroup: "cafe" },
  { action: "food", label: "맛집", excludeGroup: "food" },
  { action: "nearby", label: "볼거리", excludeGroup: null },
];

function infoChips(input: FollowUpInput): FollowChip[] {
  const id = input.contentId ?? "";
  const t = input.title;
  const entries: { key: string; chip: FollowChip }[] = [
    {
      key: `detail:about:${id}`,
      chip: {
        label: "여긴 어떤 곳이야?",
        action: { kind: "detail", followKey: "about", question: `${t}은 어떤 곳이야?` },
      },
    },
    {
      key: `detail:hours:${id}`,
      chip: {
        label: "영업시간은?",
        action: { kind: "detail", followKey: "hours", question: `${t} 영업시간 알려줘` },
      },
    },
    {
      key: `anchor:related:${id}`,
      chip: {
        label: "연관 관광지는?",
        action: { kind: "anchor", action: "related", question: `${t} 연관 관광지는?` },
      },
    },
    {
      key: `detail:parking:${id}`,
      chip: {
        label: "주차는 돼?",
        action: { kind: "detail", followKey: "parking", question: `${t} 주차 돼?` },
      },
    },
    {
      key: `detail:fee:${id}`,
      chip: {
        label: "이용요금은?",
        action: { kind: "detail", followKey: "fee", question: `${t} 이용요금 알려줘` },
      },
    },
  ];
  return entries.filter((e) => !input.asked.has(e.key)).map((e) => e.chip);
}

function nearOptionChips(input: FollowUpInput): FollowChip[] {
  const id = input.contentId ?? "";
  return NEAR_OPTIONS.filter(
    (o) =>
      !input.asked.has(`anchor:${o.action}:${id}`) &&
      (o.excludeGroup === null || o.excludeGroup !== input.categoryGroup),
  ).map((o) => ({
    label: o.label,
    action: { kind: "anchor", action: o.action, question: `${input.title} 근처 ${o.label}` },
  }));
}

function nearBranch(input: FollowUpInput): FollowUpBlock {
  const id = input.contentId ?? "";
  const chips = nearOptionChips(input);
  if (input.hasCrowd && !input.asked.has(`anchor:crowd:${id}`)) {
    chips.push({
      label: "지금 붐벼?",
      action: { kind: "anchor", action: "crowd", question: `${input.title} 지금 붐벼?` },
    });
  }
  const capped = chips.slice(0, MAX_FOLLOW_CHIPS);
  capped.push({ label: "‹ 뒤로", action: { kind: "branch", to: "root" } });
  return { line: "어떤 곳부터 찾아볼까요?", chips: capped };
}

function rootBranch(input: FollowUpInput): FollowUpBlock {
  const nearAlive = nearOptionChips(input).length > 0;
  const nearChip: FollowChip = { label: "근처 뭐 있어?", action: { kind: "branch", to: "near" } };
  const chips: FollowChip[] = [];
  let line: string;
  if (input.contentId === null) {
    line = "내 위치 근처의 카페·맛집·볼거리를 찾아드릴 수 있어요.";
    if (nearAlive) chips.push(nearChip);
  } else if (input.isDetailTurn) {
    line = "더 궁금한 게 있으세요?";
    chips.push(...infoChips(input));
    if (nearAlive) chips.push(nearChip);
  } else {
    line = `${input.title} 근처의 카페·맛집·볼거리를 찾아드릴 수도 있고, 어떤 곳인지 더 알려드릴 수도 있어요.`;
    if (nearAlive) chips.push(nearChip);
    chips.push(...infoChips(input).slice(0, 1));
  }
  for (const r of input.refinements ?? []) {
    chips.push({ label: r.label, action: { kind: "refine", label: r.label, patch: r.patch } });
  }
  for (const q of input.suggestions ?? []) {
    if (input.asked.has(`q:${q}`)) continue;
    chips.push({ label: q, action: { kind: "question", question: q } });
  }
  return { line, chips: chips.slice(0, MAX_FOLLOW_CHIPS) };
}

export function followUps(input: FollowUpInput): FollowUpBlock {
  return input.branch === "near" ? nearBranch(input) : rootBranch(input);
}
