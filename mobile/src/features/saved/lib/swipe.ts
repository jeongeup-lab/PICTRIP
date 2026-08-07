export const SWIPE_ACTION_WIDTH = 92;

const CAPTURE_DX = 8;
const AXIS_RATIO = 1.6;
const OVERSHOOT_RESISTANCE = 3;
const MAX_OFFSET = -SWIPE_ACTION_WIDTH * 1.9;
const DELETE_OFFSET = -SWIPE_ACTION_WIDTH * 1.7;
const OPEN_OFFSET = -SWIPE_ACTION_WIDTH * 0.5;
const FLICK_VELOCITY = 0.35;

export type SwipeOutcome = "open" | "closed" | "delete";

export function shouldCaptureSwipe(dx: number, dy: number): boolean {
  return Math.abs(dx) > CAPTURE_DX && Math.abs(dx) > Math.abs(dy) * AXIS_RATIO;
}

export function swipeOffset(dx: number, wasOpen: boolean): number {
  const base = wasOpen ? -SWIPE_ACTION_WIDTH : 0;
  const raw = base + dx;
  if (raw >= 0) return 0;
  if (raw >= -SWIPE_ACTION_WIDTH) return raw;
  const overshoot = (raw + SWIPE_ACTION_WIDTH) / OVERSHOOT_RESISTANCE;
  return Math.max(MAX_OFFSET, -SWIPE_ACTION_WIDTH + overshoot);
}

export function swipeOutcome(offset: number, vx: number): SwipeOutcome {
  if (offset <= DELETE_OFFSET) return "delete";
  if (vx <= -FLICK_VELOCITY) return "open";
  if (vx >= FLICK_VELOCITY) return "closed";
  return offset <= OPEN_OFFSET ? "open" : "closed";
}

export function restOffset(outcome: SwipeOutcome): number {
  return outcome === "closed" ? 0 : -SWIPE_ACTION_WIDTH;
}
