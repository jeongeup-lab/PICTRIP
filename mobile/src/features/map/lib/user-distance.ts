import { haversineMeters, type LatLng } from "@/features/map/lib/geo";
import type { NearbySpot } from "@/lib/api-types";

/** Server `dist` is measured from the query-bbox center, which drifts from the
 * user as the map pans. The list must show the distance from the user's actual
 * position, so replace it with a GPS-based haversine — or null it (hidden in
 * the card) when there is no GPS fix rather than show a misleading number. */
export function withUserDistance(spots: NearbySpot[], gps: LatLng | null): NearbySpot[] {
  return spots.map((spot) => ({
    ...spot,
    dist:
      gps && spot.mapy != null && spot.mapx != null
        ? haversineMeters(gps, { lat: spot.mapy, lng: spot.mapx })
        : null,
  }));
}
