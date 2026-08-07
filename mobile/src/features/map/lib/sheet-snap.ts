import { snapYFromVisible, type SheetSnap } from "@/lib/sheet-snap";

export type { SheetSnap };

export const HANDLE_ZONE_PX = 30;
export const CHIPS_PX = 46;
export const CARD_PX = 106;
export const DEFAULT_TAB_BAR_PX = 83;
export const PEEK_MARGIN_PX = 0;
export const PEEK_VISIBLE_PX =
  HANDLE_ZONE_PX + CHIPS_PX + CARD_PX + DEFAULT_TAB_BAR_PX + PEEK_MARGIN_PX;
export const HALF_VISIBLE_PX = PEEK_VISIBLE_PX + CARD_PX;

export function sheetSnapY(
  screenH: number,
  tabBarPx: number = DEFAULT_TAB_BAR_PX,
): Record<SheetSnap, number> {
  const peek = HANDLE_ZONE_PX + CHIPS_PX + CARD_PX + PEEK_MARGIN_PX + tabBarPx;
  return snapYFromVisible(screenH, { peek, half: peek + CARD_PX });
}
