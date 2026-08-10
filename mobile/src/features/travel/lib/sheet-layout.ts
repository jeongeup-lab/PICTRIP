export type SheetSnap = "collapsed" | "mid" | "full";

export const SHEET_ANIM_MS = 280;
export const SHEET_MID_RATIO = 0.58;
export const SHEET_FULL_RATIO = 0.88;
export const SHEET_HEADER_PX = 20;
export const SHEET_FLING_VY = 0.55;

export const SHEET_SNAPS: SheetSnap[] = ["collapsed", "mid", "full"];

interface HeightInput {
  snap: SheetSnap;
  frameH: number;
  insetTop: number;
  insetBottom: number;
  keyboardPx: number;
  dockPx: number;
}

export function sheetHeightPx({ snap, frameH, insetTop, keyboardPx, dockPx }: HeightInput): number {
  if (snap === "collapsed") return dockPx + SHEET_HEADER_PX;
  const ratio = snap === "mid" ? SHEET_MID_RATIO : SHEET_FULL_RATIO;
  const wanted = Math.round(frameH * ratio);
  if (keyboardPx === 0) return wanted;
  return Math.min(wanted, frameH - keyboardPx - insetTop);
}

export function sheetBottomPx({ keyboardPx }: { keyboardPx: number }): number {
  return keyboardPx;
}

export function snapHeights(input: Omit<HeightInput, "snap">): Record<SheetSnap, number> {
  return {
    collapsed: sheetHeightPx({ ...input, snap: "collapsed" }),
    mid: sheetHeightPx({ ...input, snap: "mid" }),
    full: sheetHeightPx({ ...input, snap: "full" }),
  };
}

export function clampToSheet(height: number, heights: Record<SheetSnap, number>): number {
  return Math.min(Math.max(height, heights.collapsed), heights.full);
}

export function settleSnap({
  heights,
  from,
  height,
  velocityY,
}: {
  heights: Record<SheetSnap, number>;
  from: SheetSnap;
  height: number;
  velocityY: number;
}): SheetSnap {
  if (velocityY <= -SHEET_FLING_VY) return nextSnap(from, 1);
  if (velocityY >= SHEET_FLING_VY) return nextSnap(from, -1);
  return nearestSnap(heights, height);
}

export function nearestSnap(heights: Record<SheetSnap, number>, height: number): SheetSnap {
  return SHEET_SNAPS.reduce((best, snap) =>
    Math.abs(heights[snap] - height) < Math.abs(heights[best] - height) ? snap : best,
  );
}

export function nextSnap(from: SheetSnap, step: 1 | -1): SheetSnap {
  const at = SHEET_SNAPS.indexOf(from);
  return SHEET_SNAPS[Math.min(Math.max(at + step, 0), SHEET_SNAPS.length - 1)];
}
