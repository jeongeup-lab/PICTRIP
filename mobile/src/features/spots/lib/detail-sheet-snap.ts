export const HERO_BELOW_FOLD_PX = 92;
export const HERO_PAD_BOTTOM_PX = 22;
export const GALLERY_STRIP_PX = 258;
export const HERO_PEEK_BELOW_FOLD_PX = HERO_BELOW_FOLD_PX + GALLERY_STRIP_PX;
export const BASE_MARGIN_PX = 8;
export const MIN_BASE_VISIBLE_PX = 160;
export const MIN_PEEK_VISIBLE_PX = 120;

export type DetailSnap = "peek" | "base" | "full";

export interface DetailSnapY {
  peek: number;
  base: number;
  full: number;
}

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
