import { useQuery } from "@tanstack/react-query";
import type { LatLng } from "@/features/map/lib/geo";
import type { NearbyCategory } from "@/features/map/lib/nearby-categories";
import { getNearby, getRegionLabel, getRegionsTree } from "@/features/map/api";

/** Nearby spots for the current center + category. Disabled until a center exists. */
export function useNearbyMap(center: LatLng | null, category: NearbyCategory | null) {
  return useQuery({
    queryKey: ["map-nearby", center?.lat, center?.lng, category],
    queryFn: () => getNearby(center!.lat, center!.lng, category),
    enabled: center != null,
  });
}

/** Reverse-geocoded header label for the current center. */
export function useRegionLabel(center: LatLng | null, enabled: boolean) {
  return useQuery({
    queryKey: ["region-label", center?.lat, center?.lng],
    queryFn: () => getRegionLabel(center!.lat, center!.lng),
    enabled: enabled && center != null,
  });
}

/** Static 시도/시군구 tree — cached long (rarely changes). */
export function useRegionsTree() {
  return useQuery({
    queryKey: ["regions-tree"],
    queryFn: getRegionsTree,
    staleTime: 24 * 60 * 60 * 1000,
  });
}
