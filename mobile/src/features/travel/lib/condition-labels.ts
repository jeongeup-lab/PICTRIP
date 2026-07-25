import {
  DEFAULT_CONDITIONS,
  type Conditions,
  type RegionFilter,
  type WhenFilter,
  type WhoFilter,
} from "@/features/travel/api";

export interface ConditionOption<V extends string> {
  value: V;
  label: string;
}

export const REGION_OPTIONS: readonly ConditionOption<RegionFilter>[] = [
  { value: "all", label: "전국" },
  { value: "capital", label: "수도권" },
  { value: "gangwon", label: "강원" },
  { value: "chungcheong", label: "충청" },
  { value: "jeolla", label: "전라" },
  { value: "gyeongsang", label: "경상" },
  { value: "jeju", label: "제주" },
];

export const WHEN_OPTIONS: readonly ConditionOption<WhenFilter>[] = [
  { value: "any", label: "상관없음" },
  { value: "today", label: "오늘" },
  { value: "weekend", label: "이번 주말" },
  { value: "next_week", label: "다음 주" },
];

export const WHO_OPTIONS: readonly ConditionOption<WhoFilter>[] = [
  { value: "any", label: "상관없음" },
  { value: "solo", label: "혼자" },
  { value: "duo", label: "둘이" },
  { value: "kids", label: "아이와" },
  { value: "pets", label: "반려견과" },
];

export const NEUTRAL_CHIP_LABEL = "조건";

function labelOf<V extends string>(options: readonly ConditionOption<V>[], value: V): string {
  return options.find((o) => o.value === value)?.label ?? "";
}

export function conditionChipLabel(conditions: Conditions): string {
  const parts = [
    conditions.region === DEFAULT_CONDITIONS.region
      ? null
      : labelOf(REGION_OPTIONS, conditions.region),
    conditions.when === DEFAULT_CONDITIONS.when ? null : labelOf(WHEN_OPTIONS, conditions.when),
    conditions.who === DEFAULT_CONDITIONS.who ? null : labelOf(WHO_OPTIONS, conditions.who),
  ].filter((p): p is string => !!p);
  return parts.length > 0 ? parts.join(" · ") : NEUTRAL_CHIP_LABEL;
}

export function isNeutral(conditions: Conditions): boolean {
  return conditionChipLabel(conditions) === NEUTRAL_CHIP_LABEL;
}
