import type { RegionLabel } from "@/lib/api-types";

export type AnchorSource = "gps" | "region" | "pan";

/** Fallback once /map/region resolves but can't name the area — the backend
 * fail-opens to `ok(null)` on Kakao Local errors, and a null success would
 * otherwise leave the header on "위치 확인 중" forever. */
export const NEAR_ME_LABEL: RegionLabel = {
  sido: null,
  sigungu: null,
  dong: null,
  label: "내 주변",
};

/** Header label per S05 §0 rule 4: GPS shows a `현위치 · {동}` prefix; region
 * selection / pan-search show the bare region name. */
export function formatHeaderLabel(source: AnchorSource, label: RegionLabel | null): string {
  if (!label) return "위치 확인 중";
  if (source === "gps") return `현위치 · ${label.dong ?? label.label}`;
  return label.label;
}
