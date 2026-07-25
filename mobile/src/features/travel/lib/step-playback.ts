export const STEP_INTERVAL_MS = 760;
export const ANSWER_DELAY_MS = 240;

export interface StepProgress {
  shown: number;
  completed: number;
  finished: boolean;
}

export function playbackDurationMs(stepCount: number): number {
  return stepCount > 0 ? stepCount * STEP_INTERVAL_MS + ANSWER_DELAY_MS : 0;
}

export function stepProgressAt(stepCount: number, elapsedMs: number): StepProgress {
  if (stepCount <= 0) return { shown: 0, completed: 0, finished: true };
  const elapsed = Math.max(0, elapsedMs);
  const ticks = Math.floor(elapsed / STEP_INTERVAL_MS);
  const completed = Math.min(stepCount, ticks);
  const shown = Math.min(stepCount, ticks + 1);
  return { shown, completed, finished: elapsed >= playbackDurationMs(stepCount) };
}

export function playbackTicks(stepCount: number): number[] {
  const ticks: number[] = [];
  for (let i = 1; i <= stepCount; i += 1) ticks.push(i * STEP_INTERVAL_MS);
  ticks.push(playbackDurationMs(stepCount));
  return ticks;
}
