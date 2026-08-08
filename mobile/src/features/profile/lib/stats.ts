import { regionCount } from "@/features/saved/lib/sort";
import { SAVED_PAGE_LIMIT } from "@/features/saved/api";
import { calendarDaysSince } from "@/lib/local-date";
import type { SpotCard } from "@/lib/api-types";

export interface ProfileStats {
  saved: number;
  regions: number;
  days: number;
  partial: boolean;
}

export type StatKey = "saved" | "regions" | "days";

export function countLabel(value: number, partial: boolean): string {
  return partial ? `${value}+` : String(value);
}

export function daysSince(createdAt: string | null | undefined, now: number): number {
  return calendarDaysSince(createdAt, now);
}

export function profileStats(
  saved: readonly SpotCard[] | undefined,
  createdAt: string | null | undefined,
  now: number,
): ProfileStats {
  const list = saved ?? [];
  return {
    saved: list.length,
    regions: regionCount(list),
    days: daysSince(createdAt, now),
    partial: list.length >= SAVED_PAGE_LIMIT,
  };
}
