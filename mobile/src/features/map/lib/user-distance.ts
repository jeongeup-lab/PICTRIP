import { haversineMeters, type LatLng } from "@/features/map/lib/geo";
import type { NearbySpot } from "@/lib/api-types";

export function withUserDistance(spots: NearbySpot[], gps: LatLng | null): NearbySpot[] {
  return spots.map((spot) => ({
    ...spot,
    dist:
      gps && spot.mapy != null && spot.mapx != null
        ? haversineMeters(gps, { lat: spot.mapy, lng: spot.mapx })
        : null,
  }));
}
