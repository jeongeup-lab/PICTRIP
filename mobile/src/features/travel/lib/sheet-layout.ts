export type SheetSnap = "collapsed" | "mid" | "full";

export const SHEET_ANIM_MS = 280;
export const SHEET_MID_RATIO = 0.58;
export const SHEET_FULL_RATIO = 0.88;

interface HeightInput {
  snap: SheetSnap;
  frameH: number;
  insetTop: number;
  insetBottom: number;
  keyboardPx: number;
  dockPx: number;
}

export function sheetHeightPx({ snap, frameH, insetTop, keyboardPx, dockPx }: HeightInput): number {
  if (snap === "collapsed") return dockPx;
  const ratio = snap === "mid" ? SHEET_MID_RATIO : SHEET_FULL_RATIO;
  const wanted = Math.round(frameH * ratio);
  if (keyboardPx === 0) return wanted;
  return Math.min(wanted, frameH - keyboardPx - insetTop);
}

export function sheetBottomPx({ keyboardPx }: { keyboardPx: number }): number {
  return keyboardPx;
}
