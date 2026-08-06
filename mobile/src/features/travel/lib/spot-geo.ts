import type { LatLng } from "@/features/map/lib/geo";
import type { TravelSpot } from "@/features/travel/api";
import type { NearbySpot } from "@/lib/api-types";

export interface PlacedSpot {
  spot: TravelSpot;
  lat: number;
  lng: number;
}

export interface RegionGroup {
  label: string;
  count: number;
}

const EARTH_RADIUS_KM = 6371;
const MIN_SPAN_DEG = 0.02;
const MAX_NAMED_GROUPS = 2;
const SPREAD_MENTION_KM = 20;
const MINI_FIT_LAT_DEG = 2.5;

export function placed(spots: TravelSpot[]): PlacedSpot[] {
  return spots.flatMap((spot) =>
    spot.lat !== null && spot.lng !== null ? [{ spot, lat: spot.lat, lng: spot.lng }] : [],
  );
}

export function pinsFrom(spots: PlacedSpot[]): NearbySpot[] {
  return spots.map(({ spot, lat, lng }) => ({
    contentId: spot.contentId,
    title: spot.title,
    firstImageUrl: spot.imageUrl,
    addr1: spot.regionLabel,
    mapx: lng,
    mapy: lat,
    category: null,
    dist: null,
    categoryGroup: null,
    regionName: null,
    sigunguName: null,
    overview: null,
  }));
}

export function miniFitSpots(spots: PlacedSpot[]): PlacedSpot[] {
  if (spots.length === 0) return spots;
  const lats = spots.map((s) => s.lat);
  if (Math.max(...lats) - Math.min(...lats) <= MINI_FIT_LAT_DEG) return spots;
  return largestCluster(spots);
}

function largestCluster(spots: PlacedSpot[]): PlacedSpot[] {
  const buckets = new Map<string, PlacedSpot[]>();
  spots.forEach((s) => {
    const key = s.spot.regionLabel.trim().replace(/\s+/g, " ");
    buckets.set(key, [...(buckets.get(key) ?? []), s]);
  });
  return [...buckets.values()].sort((a, b) => b.length - a.length)[0] ?? spots;
}

export function center(spots: PlacedSpot[]): LatLng | null {
  if (spots.length === 0) return null;
  return {
    lat: spots.reduce((sum, s) => sum + s.lat, 0) / spots.length,
    lng: spots.reduce((sum, s) => sum + s.lng, 0) / spots.length,
  };
}

export function distanceKm(a: PlacedSpot, b: PlacedSpot): number {
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const dLat = toRad(b.lat - a.lat);
  const dLng = toRad(b.lng - a.lng);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * EARTH_RADIUS_KM * Math.asin(Math.min(1, Math.sqrt(h)));
}

export function spreadKm(spots: PlacedSpot[]): number {
  let widest = 0;
  for (let i = 0; i < spots.length; i += 1) {
    for (let j = i + 1; j < spots.length; j += 1) {
      widest = Math.max(widest, distanceKm(spots[i], spots[j]));
    }
  }
  return widest;
}

export function regionGroups(spots: PlacedSpot[]): RegionGroup[] {
  const counts = new Map<string, number>();
  spots.forEach((s) => {
    const key = s.spot.regionLabel.trim().replace(/\s+/g, " ");
    if (key) counts.set(key, (counts.get(key) ?? 0) + 1);
  });
  const keys = [...counts.keys()];
  const narrow = keys.map(areaLabel);
  return keys
    .map((key, index) => ({
      label: narrow.filter((n) => n === narrow[index]).length > 1 ? key : narrow[index],
      count: counts.get(key) ?? 0,
    }))
    .sort((a, b) => b.count - a.count);
}

function areaLabel(regionLabel: string): string {
  const parts = regionLabel.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "";
  return parts[parts.length - 1];
}

export function bounds(spots: PlacedSpot[]): { sw: LatLng; ne: LatLng } | null {
  if (spots.length === 0) return null;
  const lat = widen(spots.map((s) => s.lat));
  const lng = widen(spots.map((s) => s.lng));
  return { sw: { lat: lat.min, lng: lng.min }, ne: { lat: lat.max, lng: lng.max } };
}

function widen(values: number[]): { min: number; max: number } {
  const min = Math.min(...values);
  const max = Math.max(...values);
  if (max - min >= MIN_SPAN_DEG) return { min, max };
  const mid = (min + max) / 2;
  return { min: mid - MIN_SPAN_DEG / 2, max: mid + MIN_SPAN_DEG / 2 };
}

export function spatialSummary(spots: PlacedSpot[]): string | null {
  if (spots.length < 2) return null;
  const groups = regionGroups(spots);
  if (groups.length === 0) return null;
  const spread = spreadKm(spots);
  const tail =
    spread >= SPREAD_MENTION_KM ? ` 가장 먼 두 곳은 ${Math.round(spread)}km 떨어져요.` : "";

  if (groups.length === 1) return `모두 ${groups[0].label}에 있어요.${tail}`;
  const named = groups
    .slice(0, MAX_NAMED_GROUPS)
    .map((g) => `${g.label} ${g.count}곳`)
    .join(" · ");
  const rest = groups.length - MAX_NAMED_GROUPS;
  return rest > 0
    ? `${named} 등 ${groups.length}곳으로 나뉘어요.${tail}`
    : `${named}이에요.${tail}`;
}
