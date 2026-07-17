export type SheetSnap = "peek" | "half" | "full";

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
  const full = screenH * 0.08;
  const peekVisible = HANDLE_ZONE_PX + CHIPS_PX + CARD_PX + PEEK_MARGIN_PX + tabBarPx;
  const halfVisible = peekVisible + CARD_PX;
  return {
    peek: screenH - peekVisible,
    half: Math.max(full + 1, screenH - halfVisible),
    full,
  };
}
