import { snapYFromVisible, type SheetSnap } from "@/lib/sheet-snap";

export type { SheetSnap };

export const HANDLE_ZONE_PX = 30;
export const FIELD_PX = 62;
export const CHIPS_PX = 45;
export const START_PX = 152;
export const ROWS_PX = 196;
export const DEFAULT_TAB_BAR_PX = 83;

export const TAB_BAR_CONTENT_PX = 49;

export function travelSheetSnapY(
  screenH: number,
  tabBarPx: number = DEFAULT_TAB_BAR_PX,
): Record<SheetSnap, number> {
  const peek = HANDLE_ZONE_PX + FIELD_PX + CHIPS_PX + START_PX + tabBarPx;
  return snapYFromVisible(screenH, { peek, half: peek + ROWS_PX });
}

export function sheetHeightOverRoot(screenH: number, tabBarPx: number, snapYValue: number): number {
  return Math.max(0, screenH - tabBarPx - snapYValue);
}
