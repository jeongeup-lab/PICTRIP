import { SEARCH_HERE_RATIO } from "@/constants/map";
import { haversineMeters, type LatLng } from "@/features/map/lib/geo";

/** True when the panned viewport center has drifted past SEARCH_HERE_RATIO of
 * the query radius from the last fetched center — the cue to surface the
 * "이 지역에서 검색" pill (S05 §1.4). */
export function shouldShowSearchHere(
  viewport: LatLng | null,
  lastQuery: LatLng | null,
  radius: number,
): boolean {
  if (!viewport || !lastQuery) return false;
  return haversineMeters(viewport, lastQuery) > radius * SEARCH_HERE_RATIO;
}
