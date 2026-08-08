import type { LatLng } from "@/features/map/lib/geo";
import type { TravelSpot } from "@/features/travel/api";
import type { NearbySpot } from "@/lib/api-types";

export interface PlacedSpot {
  spot: TravelSpot;
  lat: number;
  lng: number;
}

const MIN_SPAN_DEG = 0.02;

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
    categoryGroup: spot.categoryGroup ?? null,
    regionName: null,
    sigunguName: null,
    overview: null,
  }));
}

export function center(spots: PlacedSpot[]): LatLng | null {
  if (spots.length === 0) return null;
  return {
    lat: spots.reduce((sum, s) => sum + s.lat, 0) / spots.length,
    lng: spots.reduce((sum, s) => sum + s.lng, 0) / spots.length,
  };
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
