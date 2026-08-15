export function formatBaseDate(baseDate: string | null | undefined): string | null {
  if (!baseDate) return null;
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(baseDate.trim());
  if (!match) return null;
  const [, , month, day] = match;
  return `${Number(month)}월 ${Number(day)}일 기준`;
}
