import { haversineMeters, type LatLng } from "@/features/map/lib/geo";
import type { TravelSpot } from "@/features/travel/api";

export interface DistanceReading {
  value: string;
  unit: string;
}

const METERS_IN_KM = 1000;
const NEAR_KM = 10;

export function coordsOf(spot: TravelSpot): LatLng | null {
  return spot.lat !== null && spot.lng !== null ? { lat: spot.lat, lng: spot.lng } : null;
}

export function spotDistanceKm(spot: TravelSpot, origin: LatLng | null): number | null {
  const target = coordsOf(spot);
  if (!origin || !target) return null;
  return haversineMeters(origin, target) / METERS_IN_KM;
}

export function distanceReading(km: number): DistanceReading {
  if (km < 1) return { value: String(Math.max(10, Math.round(km * METERS_IN_KM))), unit: "m" };
  if (km < NEAR_KM) return { value: km.toFixed(1), unit: "km" };
  return { value: String(Math.round(km)), unit: "km" };
}
