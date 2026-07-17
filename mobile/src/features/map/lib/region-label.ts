import type { RegionLabel } from "@/lib/api-types";

export type AnchorSource = "gps" | "region" | "pan";

export const NEAR_ME_LABEL: RegionLabel = {
  sido: null,
  sigungu: null,
  dong: null,
  label: "내 주변",
};

export function formatHeaderLabel(source: AnchorSource, label: RegionLabel | null): string {
  if (!label) return "위치 확인 중";
  if (source === "gps") return `현위치 · ${label.dong ?? label.label}`;
  return label.label;
}
