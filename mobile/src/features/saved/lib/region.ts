import type { SpotCard } from "@/lib/api-types";

export function regionOf(spot: SpotCard): string | null {
  const head = spot.addr1?.trim().split(/\s+/)[0];
  return head && head.length > 0 ? head : null;
}

export function subline(spot: SpotCard): string {
  return [regionOf(spot), spot.category].filter(Boolean).join(" · ");
}

export function regionCount(list: readonly SpotCard[]): number {
  return new Set(list.map(regionOf).filter((r): r is string => r !== null)).size;
}
