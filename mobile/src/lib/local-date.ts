const MS_PER_DAY = 86_400_000;

function localDayNumber(value: Date): number {
  return Math.floor(Date.UTC(value.getFullYear(), value.getMonth(), value.getDate()) / MS_PER_DAY);
}

export function localDateLabel(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return null;
  const month = String(parsed.getMonth() + 1).padStart(2, "0");
  const day = String(parsed.getDate()).padStart(2, "0");
  return `${parsed.getFullYear()}.${month}.${day}`;
}

export function calendarDaysSince(iso: string | null | undefined, now: number): number {
  if (!iso) return 0;
  const started = new Date(iso);
  if (Number.isNaN(started.getTime())) return 0;
  return Math.max(1, localDayNumber(new Date(now)) - localDayNumber(started) + 1);
}
