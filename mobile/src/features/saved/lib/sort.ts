import { haversineMeters, type LatLng } from "@/features/map/lib/geo";
import type { SpotCard } from "@/lib/api-types";

export type SavedSort = "recent" | "near" | "region";

export interface SavedSortOption {
  mode: SavedSort;
  label: string;
}

export const SAVED_SORTS: readonly SavedSortOption[] = [
  { mode: "recent", label: "최근 저장 순" },
  { mode: "near", label: "가까운 순" },
  { mode: "region", label: "지역별" },
] as const;

export function regionOf(spot: SpotCard): string | null {
  const head = spot.addr1?.trim().split(/\s+/)[0];
  return head && head.length > 0 ? head : null;
}

export function subline(spot: SpotCard): string {
  return [regionOf(spot), spot.category].filter(Boolean).join(" · ");
}

export function distanceMeters(spot: SpotCard, from: LatLng | null): number | null {
  if (!from || spot.mapx == null || spot.mapy == null) return null;
  return haversineMeters(from, { lat: spot.mapy, lng: spot.mapx });
}

export function distanceLabel(meters: number | null): string {
  if (meters === null) return "—";
  if (meters < 1000) return `${Math.max(1, Math.round(meters / 10) * 10)}m`;
  if (meters < 10_000) return `${(meters / 1000).toFixed(1)}km`;
  return `${Math.round(meters / 1000)}km`;
}

export function sortSaved(
  list: readonly SpotCard[],
  mode: SavedSort,
  from: LatLng | null,
): SpotCard[] {
  if (mode === "recent") return [...list];
  if (mode === "near") return sortByDistance(list, from);
  return sortByRegion(list);
}

function sortByDistance(list: readonly SpotCard[], from: LatLng | null): SpotCard[] {
  return [...list]
    .map((spot, index) => ({ spot, index, meters: distanceMeters(spot, from) }))
    .sort((a, b) => {
      if (a.meters === null && b.meters === null) return a.index - b.index;
      if (a.meters === null) return 1;
      if (b.meters === null) return -1;
      return a.meters - b.meters || a.index - b.index;
    })
    .map((entry) => entry.spot);
}

function sortByRegion(list: readonly SpotCard[]): SpotCard[] {
  const order = new Map<string, number>();
  list.forEach((spot) => {
    const region = regionOf(spot);
    if (region !== null && !order.has(region)) order.set(region, order.size);
  });
  return [...list]
    .map((spot, index) => ({ spot, index, region: regionOf(spot) }))
    .sort((a, b) => {
      if (a.region === null && b.region === null) return a.index - b.index;
      if (a.region === null) return 1;
      if (b.region === null) return -1;
      const rank = (order.get(a.region) ?? 0) - (order.get(b.region) ?? 0);
      return rank !== 0 ? rank : a.index - b.index;
    })
    .map((entry) => entry.spot);
}

export function regionCount(list: readonly SpotCard[]): number {
  return new Set(list.map(regionOf).filter((r): r is string => r !== null)).size;
}
