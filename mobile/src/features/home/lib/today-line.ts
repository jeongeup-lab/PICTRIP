const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"] as const;

export function todayLine(regionLabel: string | null, now: Date = new Date()): string {
  const day = `${now.getMonth() + 1}월 ${now.getDate()}일 ${WEEKDAYS[now.getDay()]}`;
  return regionLabel ? `${day} · ${regionLabel}` : day;
}

export function scopeTitle(scope: "nearby" | "national"): string {
  return scope === "nearby" ? "오늘, 이 근처" : "오늘, 전국";
}
