/**
 * Bottom padding for the map list so the last card clears the sheet's off-screen
 * overflow plus the tab bar. The sheet (height = screen H) is translated down by
 * SHEET_SNAP_Y[snap], so it hangs that many px below the screen; the padding MUST
 * scale with that overflow, else the last card is clipped at the half/peek snaps.
 */
export function mapListPaddingBottom(
  sheetOffscreenPx: number,
  tabBarHeight: number,
  margin: number,
): number {
  return sheetOffscreenPx + tabBarHeight + margin;
}
