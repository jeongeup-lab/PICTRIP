import type { Plan, ResolvedPlace, TimeOfDay } from "@/features/plan/api";

export const TIME_OF_DAY_LABEL: Record<TimeOfDay, string> = {
  morning: "오전",
  afternoon: "오후",
  evening: "저녁",
};

export function durationLabel(days: number): string {
  return days <= 1 ? "당일 코스" : `${days - 1}박 ${days}일`;
}

export function shortDurationLabel(days: number): string {
  return days <= 1 ? "당일" : `${days - 1}박 ${days}일`;
}

export function shortRegion(address: string | null | undefined): string {
  return (address ?? "").split(" ").slice(0, 2).join(" ");
}

export function placeName(place: ResolvedPlace): string {
  return place.spot?.title ?? place.extracted.nameKo ?? place.extracted.name;
}

export function planTitle(plan: Plan): string {
  if (plan.sourceTitle) return plan.sourceTitle;
  const region = plan.days[0]?.regionLabel;
  return region ? `${region} 여행` : "이름 없는 일정";
}

export function totalSlots(plan: Plan): number {
  return plan.days.reduce((n, day) => n + day.slots.length, 0);
}

export function totalTravelMinutes(plan: Plan): number {
  return plan.days.reduce(
    (n, day) => n + day.slots.reduce((m, slot) => m + (slot.travelMinutesFromPrev ?? 0), 0),
    0,
  );
}

export function planImages(plan: Plan): string[] {
  const seen: string[] = [];
  for (const day of plan.days) {
    for (const slot of day.slots) {
      const url = slot.place.spot?.imageUrl;
      if (url && !seen.includes(url)) seen.push(url);
    }
  }
  return seen;
}

export function planThumb(plan: Plan): string | null {
  return planImages(plan)[0] ?? null;
}

export function collageImages(plan: Plan): string[] {
  const images = planImages(plan);
  if (images.length === 0) return [];
  return images.length < 3 ? images.slice(0, 1) : images.slice(0, 3);
}

export function unplacedSummary(unplaced: ResolvedPlace[]): string {
  const names = unplaced.slice(0, 5).map(placeName).join(", ");
  return unplaced.length > 5 ? `${names} 외` : names;
}
