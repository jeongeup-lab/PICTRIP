export type SheetSnap = "peek" | "half" | "full";

// Reveal budgets — how many px of the sheet stay on-screen at each snap, derived
// from the actual component heights (NOT a screen ratio) so the card count is
// stable regardless of device height: peek shows exactly ONE NearbyCard, half
// (the entry default) exactly TWO, both sitting above the tab bar.
export const HANDLE_ZONE_PX = 30; // handleZone: paddingTop 10 + grabber 4 + margin 10 + paddingBottom 6
export const CHIPS_PX = 46; // CategoryChips: chip 34 + paddingVertical 6+6
export const CARD_PX = 112; // NearbyCard: image 92 + paddingVertical 10+10
export const TAB_BAR_PX = 83; // iOS tab content 49 + typical safe-area inset ~34 (card must clear it)
export const PEEK_MARGIN_PX = 12;
export const PEEK_VISIBLE_PX = HANDLE_ZONE_PX + CHIPS_PX + CARD_PX + TAB_BAR_PX + PEEK_MARGIN_PX;
export const HALF_VISIBLE_PX = PEEK_VISIBLE_PX + CARD_PX;

/**
 * translateY of the sheet (height = screenH, top: 0) at each snap; smaller =
 * taller sheet. half is clamped below peek so the full < half < peek ordering
 * survives even on very short screens.
 */
export function sheetSnapY(screenH: number): Record<SheetSnap, number> {
  const full = screenH * 0.08;
  return {
    peek: screenH - PEEK_VISIBLE_PX,
    half: Math.max(full + 1, screenH - HALF_VISIBLE_PX),
    full,
  };
}
