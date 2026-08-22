import type { LegalSlug } from "@/features/legal/constants";

export type ConsentKey = "age" | "terms" | "privacy" | "ai" | "location";

export interface TermsItem {
  key: ConsentKey;
  required: boolean;
  label: string;
  doc?: LegalSlug;
}

/**
 * 실제로 동작하는 항목만 세운다 — 누르면 아무 일도 안 하는 행은 동의를 받은 척하는 것이다.
 * `ai` 는 아래에 상세표가 붙는다. 법 제22조상 필수와 선택은 구분해 각각 받아야 한다.
 */
export const TERMS_ITEMS: readonly TermsItem[] = [
  { key: "age", required: true, label: "만 14세 이상입니다" },
  { key: "terms", required: true, label: "서비스 이용약관", doc: "terms" },
  { key: "privacy", required: true, label: "개인정보 수집·이용", doc: "privacy" },
  { key: "ai", required: false, label: "AI 질문 처리 (개인정보 국외 이전)", doc: "privacy" },
  { key: "location", required: false, label: "위치정보 이용", doc: "location" },
] as const;

export const REQUIRED_KEYS: readonly ConsentKey[] = TERMS_ITEMS.filter((i) => i.required).map(
  (i) => i.key,
);

export type ConsentChoices = Record<ConsentKey, boolean>;

export const EMPTY_CHOICES: ConsentChoices = {
  age: false,
  terms: false,
  privacy: false,
  ai: false,
  location: false,
};

export function allChecked(choices: ConsentChoices): boolean {
  return TERMS_ITEMS.every((item) => choices[item.key]);
}

export function requiredMet(choices: ConsentChoices): boolean {
  return REQUIRED_KEYS.every((key) => choices[key]);
}

export function setAll(value: boolean): ConsentChoices {
  return TERMS_ITEMS.reduce<ConsentChoices>((acc, item) => ({ ...acc, [item.key]: value }), {
    ...EMPTY_CHOICES,
  });
}
