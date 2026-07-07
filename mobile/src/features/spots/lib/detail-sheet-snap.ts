/**
 * Snap geometry for the map's spot-detail sheet (marker tap → panel).
 *
 * The sheet is a window-height view translated down by `y` inside the map
 * screen (window minus tab bar), so at base the on-screen content is
 * `screenH - tabBarHeight - y` px. Base must reveal the hero up to just above
 * the "전체 사진" button — a content-measured height, not a screen ratio.
 */

/** Hero px hidden below the base fold when a gallery renders: 전체 사진 button
 * 56 + its marginTop 14 + hero paddingBottom 22 (Gallery/SpotHero styles). */
export const HERO_BELOW_FOLD_PX = 92;
/** Without a gallery only the hero bottom padding sits below the fold. */
export const HERO_PAD_BOTTOM_PX = 22;
/** Gap between the hero fold and the tab bar top at base. */
export const BASE_MARGIN_PX = 8;
/** Never open the base snap shorter than this (degenerate hero measurements). */
export const MIN_BASE_VISIBLE_PX = 160;

export interface DetailSnapY {
  base: number;
  full: number;
}

/**
 * @param heroAboveFoldPx measured hero height minus its below-fold block;
 *   null before the first onLayout → ~42% of the screen as a fallback.
 */
export function detailSheetSnapY(
  screenH: number,
  heroAboveFoldPx: number | null,
  tabBarHeight: number,
): DetailSnapY {
  const full = screenH * 0.08;
  const aboveFold = heroAboveFoldPx ?? Math.round(screenH * 0.42);
  const base = Math.min(
    screenH - tabBarHeight - MIN_BASE_VISIBLE_PX,
    Math.max(full + 1, screenH - tabBarHeight - aboveFold - BASE_MARGIN_PX),
  );
  return { base, full };
}
