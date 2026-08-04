import type { LatLng } from "@/features/map/lib/geo";
import type { TravelSpot } from "@/features/travel/api";

export interface PlacedSpot {
  spot: TravelSpot;
  lat: number;
  lng: number;
}

export interface PreviewPoint {
  contentId: string;
  x: number;
  y: number;
}

export interface RegionGroup {
  label: string;
  count: number;
}

const EARTH_RADIUS_KM = 6371;
const SINGLE_SPAN_DEG = 0.02;
const MAX_NAMED_GROUPS = 2;
const SPREAD_MENTION_KM = 20;

export function placed(spots: TravelSpot[]): PlacedSpot[] {
  return spots.flatMap((spot) =>
    spot.lat !== null && spot.lng !== null ? [{ spot, lat: spot.lat, lng: spot.lng }] : [],
  );
}

export function previewPoints(
  spots: PlacedSpot[],
  { width, height, padding }: { width: number; height: number; padding: number },
): PreviewPoint[] {
  if (spots.length === 0) return [];
  const lats = spots.map((s) => s.lat);
  const lngs = spots.map((s) => s.lng);
  const spanLat = Math.max(Math.max(...lats) - Math.min(...lats), SINGLE_SPAN_DEG);
  const spanLng = Math.max(Math.max(...lngs) - Math.min(...lngs), SINGLE_SPAN_DEG);
  const midLat = (Math.max(...lats) + Math.min(...lats)) / 2;
  const midLng = (Math.max(...lngs) + Math.min(...lngs)) / 2;
  const inner = { w: width - padding * 2, h: height - padding * 2 };
  const place = (ratio: number, span: number, offset: number) =>
    padding + span * Math.min(1, Math.max(0, ratio)) + offset;
  return spots.map((s) => ({
    contentId: s.spot.contentId,
    x: place(0.5 + (s.lng - midLng) / spanLng, inner.w, 0),
    y: place(0.5 - (s.lat - midLat) / spanLat, inner.h, 0),
  }));
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
  const lats = spots.map((s) => s.lat);
  const lngs = spots.map((s) => s.lng);
  return {
    sw: { lat: Math.min(...lats), lng: Math.min(...lngs) },
    ne: { lat: Math.max(...lats), lng: Math.max(...lngs) },
  };
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
