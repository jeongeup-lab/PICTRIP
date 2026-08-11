const MINUTE_MS = 60_000;
const HOUR_MS = 60 * MINUTE_MS;

export function formatUpdatedAt(updatedAt: number, now: number): string | null {
  if (!updatedAt) return null;
  const elapsed = Math.max(0, now - updatedAt);
  if (elapsed < MINUTE_MS) return "방금 전 업데이트";
  if (elapsed < HOUR_MS) return `${Math.floor(elapsed / MINUTE_MS)}분 전 업데이트`;
  return `${Math.floor(elapsed / HOUR_MS)}시간 전 업데이트`;
}
