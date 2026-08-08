export type LegalSlug = "terms" | "privacy" | "location";

export interface LegalDoc {
  slug: LegalSlug;
  title: string;
}

export const LEGAL_DOCS: readonly LegalDoc[] = [
  { slug: "terms", title: "이용약관" },
  { slug: "privacy", title: "개인정보처리방침" },
  { slug: "location", title: "위치기반서비스 이용약관" },
] as const;

export const LEGAL_BASE_URL = "https://pictrip.org/legal";

export function legalUrl(slug: LegalSlug): string {
  return `${LEGAL_BASE_URL}/${slug}`;
}

export function findLegalDoc(slug: string): LegalDoc | undefined {
  return LEGAL_DOCS.find((d) => d.slug === slug);
}
