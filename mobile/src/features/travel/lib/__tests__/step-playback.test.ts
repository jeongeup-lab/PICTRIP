import {
  ANSWER_DELAY_MS,
  playbackDurationMs,
  playbackTicks,
  stepProgressAt,
  STEP_INTERVAL_MS,
} from "@/features/travel/lib/step-playback";

describe("playbackDurationMs", () => {
  it("holds three steps for about 2.3 seconds", () => {
    expect(playbackDurationMs(3)).toBe(3 * STEP_INTERVAL_MS + ANSWER_DELAY_MS);
    expect(playbackDurationMs(3)).toBe(2520);
  });

  it("is zero when the server ran no steps", () => {
    expect(playbackDurationMs(0)).toBe(0);
  });
});

describe("stepProgressAt", () => {
  it("shows the first step immediately with nothing completed", () => {
    expect(stepProgressAt(3, 0)).toEqual({ shown: 1, completed: 0, finished: false });
  });

  it("completes a step exactly when the next one appears", () => {
    expect(stepProgressAt(3, STEP_INTERVAL_MS)).toEqual({
      shown: 2,
      completed: 1,
      finished: false,
    });
  });

  it("never shows more steps than the server ran", () => {
    const progress = stepProgressAt(3, 10 * STEP_INTERVAL_MS);
    expect(progress.shown).toBe(3);
    expect(progress.completed).toBe(3);
  });

  it("only finishes after the trailing answer delay", () => {
    expect(stepProgressAt(3, 3 * STEP_INTERVAL_MS).finished).toBe(false);
    expect(stepProgressAt(3, playbackDurationMs(3)).finished).toBe(true);
  });

  it("treats an empty step list as already finished", () => {
    expect(stepProgressAt(0, 0)).toEqual({ shown: 0, completed: 0, finished: true });
  });

  it("clamps negative elapsed time to the start", () => {
    expect(stepProgressAt(2, -500)).toEqual({ shown: 1, completed: 0, finished: false });
  });
});

describe("playbackTicks", () => {
  it("schedules one tick per step plus the answer reveal", () => {
    expect(playbackTicks(3)).toEqual([760, 1520, 2280, 2520]);
  });
});
