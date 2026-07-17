import { SEARCH_HERE_RATIO } from "@/constants/map";
import { haversineMeters, type LatLng } from "@/features/map/lib/geo";

export function shouldShowSearchHere(
  viewport: LatLng | null,
  lastQuery: LatLng | null,
  radius: number,
): boolean {
  if (!viewport || !lastQuery) return false;
  return haversineMeters(viewport, lastQuery) > radius * SEARCH_HERE_RATIO;
}
