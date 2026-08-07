export type SheetSnap = "peek" | "half" | "full";

export const SHEET_SNAPS: SheetSnap[] = ["full", "half", "peek"];

export const FULL_TOP_RATIO = 0.08;

export function snapYFromVisible(
  screenH: number,
  visible: { peek: number; half: number },
): Record<SheetSnap, number> {
  const full = screenH * FULL_TOP_RATIO;
  return {
    peek: screenH - visible.peek,
    half: Math.max(full + 1, screenH - visible.half),
    full,
  };
}

export function nearestSnap(landingY: number, snapY: Record<SheetSnap, number>): SheetSnap {
  return SHEET_SNAPS.reduce((best, s) =>
    Math.abs(snapY[s] - landingY) < Math.abs(snapY[best] - landingY) ? s : best,
  );
}
