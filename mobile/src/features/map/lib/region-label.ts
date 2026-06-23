import type { RegionLabel } from "@/lib/api-types";

export type AnchorSource = "gps" | "region" | "pan";

/** Header label per S05 §0 rule 4: GPS shows a `현위치 · {동}` prefix; region
 * selection / pan-search show the bare region name. */
export function formatHeaderLabel(source: AnchorSource, label: RegionLabel | null): string {
  if (!label) return "위치 확인 중";
  if (source === "gps") return `현위치 · ${label.dong ?? label.label}`;
  return label.label;
}
