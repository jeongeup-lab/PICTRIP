export type SheetSnap = "peek" | "half" | "full";

// Reveal budgets — how many px of the sheet stay on-screen at each snap, derived
// from the actual component heights (NOT a screen ratio) so the card count is
// stable regardless of device height: peek shows exactly ONE NearbyCard, half
// (the entry default) exactly TWO, both sitting above the tab bar.
export const HANDLE_ZONE_PX = 30; // handleZone: paddingTop 10 + grabber 4 + margin 10 + paddingBottom 6
export const CHIPS_PX = 46; // CategoryChips: chip 34 + paddingVertical 6+6
export const CARD_PX = 112; // NearbyCard: image 92 + paddingVertical 10+10
// Fallback tab-bar height (iOS 49 content + typical 34 home-indicator inset) for
// the module-level SHEET_SNAP_Y constant. The map screen passes the REAL height
// (49 + insets.bottom) so the reveal is exact on every device — a fixed 83 over-
// reveals on phones with a smaller bottom inset (e.g. SE-class → extra ~34px).
export const DEFAULT_TAB_BAR_PX = 83;
// No slack: peek reveals exactly ONE card, half exactly TWO, last card flush with
// the tab-bar top. (Was 12 — the sliver of the next card read as "a bit more".)
export const PEEK_MARGIN_PX = 0;
export const PEEK_VISIBLE_PX =
  HANDLE_ZONE_PX + CHIPS_PX + CARD_PX + DEFAULT_TAB_BAR_PX + PEEK_MARGIN_PX;
export const HALF_VISIBLE_PX = PEEK_VISIBLE_PX + CARD_PX;

/**
 * translateY of the sheet (height = screenH, top: 0) at each snap; smaller =
 * taller sheet. half is clamped below peek so the full < half < peek ordering
 * survives even on very short screens. `tabBarPx` defaults to DEFAULT_TAB_BAR_PX;
 * the map screen passes the device-measured height for an exact card count.
 */
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
