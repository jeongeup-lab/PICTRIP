export function mapListPaddingBottom(
  sheetOffscreenPx: number,
  tabBarHeight: number,
  margin: number,
): number {
  return sheetOffscreenPx + tabBarHeight + margin;
}
