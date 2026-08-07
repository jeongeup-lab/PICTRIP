import {
  SWIPE_ACTION_WIDTH,
  restOffset,
  shouldCaptureSwipe,
  swipeOffset,
  swipeOutcome,
} from "@/features/saved/lib/swipe";

describe("shouldCaptureSwipe", () => {
  it("ignores taps and short jitters", () => {
    expect(shouldCaptureSwipe(0, 0)).toBe(false);
    expect(shouldCaptureSwipe(-5, 1)).toBe(false);
  });

  it("ignores vertical scrolls", () => {
    expect(shouldCaptureSwipe(-20, -40)).toBe(false);
  });

  it("captures a clear horizontal drag", () => {
    expect(shouldCaptureSwipe(-24, 6)).toBe(true);
    expect(shouldCaptureSwipe(24, -6)).toBe(true);
  });
});

describe("swipeOffset", () => {
  it("never opens to the right", () => {
    expect(swipeOffset(40, false)).toBe(0);
    expect(swipeOffset(200, true)).toBe(0);
  });

  it("follows the finger up to the action width", () => {
    expect(swipeOffset(-40, false)).toBe(-40);
    expect(swipeOffset(-SWIPE_ACTION_WIDTH, false)).toBe(-SWIPE_ACTION_WIDTH);
  });

  it("resists past the action width", () => {
    const past = swipeOffset(-SWIPE_ACTION_WIDTH - 60, false);
    expect(past).toBeLessThan(-SWIPE_ACTION_WIDTH);
    expect(past).toBeGreaterThan(-SWIPE_ACTION_WIDTH - 60);
  });

  it("continues from an already open row", () => {
    expect(swipeOffset(-10, true)).toBe(-SWIPE_ACTION_WIDTH - 10 / 3);
    expect(swipeOffset(30, true)).toBe(-SWIPE_ACTION_WIDTH + 30);
  });
});

describe("swipeOutcome", () => {
  it("snaps back on a short drag", () => {
    expect(swipeOutcome(-20, 0)).toBe("closed");
  });

  it("opens past half the action width", () => {
    expect(swipeOutcome(-SWIPE_ACTION_WIDTH * 0.6, 0)).toBe("open");
  });

  it("opens on a fast left flick even when barely dragged", () => {
    expect(swipeOutcome(-12, -0.9)).toBe("open");
  });

  it("closes on a fast right flick even when far open", () => {
    expect(swipeOutcome(-SWIPE_ACTION_WIDTH, 0.9)).toBe("closed");
  });

  it("deletes on a long swipe", () => {
    expect(swipeOutcome(-SWIPE_ACTION_WIDTH * 1.8, 0)).toBe("delete");
    expect(swipeOutcome(-SWIPE_ACTION_WIDTH * 1.8, 0.9)).toBe("delete");
  });
});

describe("restOffset", () => {
  it("rests closed or at the action width", () => {
    expect(restOffset("closed")).toBe(0);
    expect(restOffset("open")).toBe(-SWIPE_ACTION_WIDTH);
    expect(restOffset("delete")).toBe(-SWIPE_ACTION_WIDTH);
  });
});
