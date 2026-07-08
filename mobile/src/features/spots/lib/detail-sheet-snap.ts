/**
 * Snap geometry for the map's spot-detail sheet (marker tap → panel).
 *
 * The sheet is a window-height view translated down by `y` inside the map
 * screen (window minus tab bar), so at each snap the on-screen content is
 * `screenH - tabBarHeight - y` px. Three snaps:
 *   - base  reveals the hero up to just above the "전체 사진" button (entry).
 *   - peek  reveals the hero up to just below the lead text, above the photo
 *           strip (the "내림" state — keeps the detail open; ✕ returns to list).
 *   - full  the whole scrollable detail.
 * All content-measured (hero height), not screen ratios.
 */

/** Hero px hidden below the BASE fold when a gallery renders: 전체 사진 button
 * 56 + its marginTop 14 + hero paddingBottom 22 (Gallery/SpotHero styles). */
export const HERO_BELOW_FOLD_PX = 92;
/** Without a gallery only the hero bottom padding sits below the fold. */
export const HERO_PAD_BOTTOM_PX = 22;
/** Gallery strip block above the base fold: tile 236 + its marginTop 22. Peek
 * folds this away too, stopping just below the lead text / above the photos. */
export const GALLERY_STRIP_PX = 258;
/** Hero px hidden below the PEEK fold: base block + the photo strip. */
export const HERO_PEEK_BELOW_FOLD_PX = HERO_BELOW_FOLD_PX + GALLERY_STRIP_PX;
/** Gap between the revealed fold and the tab bar top. */
export const BASE_MARGIN_PX = 8;
/** Never open the base snap shorter than this (degenerate hero measurements). */
export const MIN_BASE_VISIBLE_PX = 160;
/** Never open the peek snap shorter than this (title/subline must stay visible). */
export const MIN_PEEK_VISIBLE_PX = 120;

export type DetailSnap = "peek" | "base" | "full";

export interface DetailSnapY {
  peek: number;
  base: number;
  full: number;
}

/** translateY of the sheet at a snap that reveals `aboveFold` px of the hero. */
function snapForFold(
  screenH: number,
  tabBarHeight: number,
  aboveFold: number,
  minVisible: number,
  floor: number,
): number {
  return Math.min(
    screenH - tabBarHeight - minVisible,
    Math.max(floor, screenH - tabBarHeight - aboveFold - BASE_MARGIN_PX),
  );
}

/**
 * @param heroH measured hero height; null before the first onLayout → ~42% of
 *   the screen as a fallback (peek collapses to base until measured).
 * @param hasGallery whether a photo strip renders (peek only differs from base
 *   when there are photos to fold away).
 */
export function detailSheetSnapY(
  screenH: number,
  heroH: number | null,
  tabBarHeight: number,
  hasGallery: boolean,
): DetailSnapY {
  const full = screenH * 0.08;
  const baseBelowFold = hasGallery ? HERO_BELOW_FOLD_PX : HERO_PAD_BOTTOM_PX;
  const baseAboveFold =
    heroH == null ? Math.round(screenH * 0.42) : Math.max(0, heroH - baseBelowFold);
  const base = snapForFold(screenH, tabBarHeight, baseAboveFold, MIN_BASE_VISIBLE_PX, full + 1);

  if (!hasGallery || heroH == null) {
    return { peek: base, base, full };
  }
  const peekAboveFold = Math.max(0, heroH - HERO_PEEK_BELOW_FOLD_PX);
  const peek = snapForFold(screenH, tabBarHeight, peekAboveFold, MIN_PEEK_VISIBLE_PX, base + 1);
  return { peek, base, full };
}
