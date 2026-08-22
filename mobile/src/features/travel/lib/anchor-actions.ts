import type { AnchorAction } from "@/features/travel/api";

export interface FocusedSpot {
  contentId: string;
  title: string;
}

export interface AnchorChoice {
  action: AnchorAction;
  label: string;
}

export const ANCHOR_CHOICES: AnchorChoice[] = [
  { action: "food", label: "근처 맛집" },
  { action: "cafe", label: "근처 카페" },
  { action: "nearby", label: "근처 볼거리" },
  { action: "crowd", label: "혼잡도" },
  { action: "related", label: "닮은 곳" },
];

export function anchorQuestion(title: string, label: string): string {
  return `${title} ${label}`;
}
