import { regionCount } from "@/features/saved/lib/sort";
import { SAVED_PAGE_LIMIT } from "@/features/saved/api";
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

const MS_PER_DAY = 86_400_000;

export function daysSince(createdAt: string | null | undefined, now: number): number {
  if (!createdAt) return 0;
  const started = Date.parse(createdAt);
  if (Number.isNaN(started)) return 0;
  return Math.max(1, Math.floor((now - started) / MS_PER_DAY) + 1);
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
