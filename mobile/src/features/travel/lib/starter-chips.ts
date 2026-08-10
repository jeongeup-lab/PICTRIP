import type { AnchorAction } from "@/features/travel/api";

export interface NearChip {
  label: string;
  action: AnchorAction;
}

export const NEAR_CHIPS: NearChip[] = [
  { label: "근처 카페", action: "cafe" },
  { label: "근처 맛집", action: "food" },
  { label: "근처 볼거리", action: "nearby" },
];

export function nearChips(): NearChip[] {
  return NEAR_CHIPS;
}
