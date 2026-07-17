import { useQuery } from "@tanstack/react-query";
import type { Bounds, LatLng } from "@/features/map/lib/geo";
import type { NearbyCategory } from "@/features/map/lib/nearby-categories";
import { getNearby, getRegionLabel } from "@/features/map/api";

export function useNearbyMap(bounds: Bounds | null, category: NearbyCategory | null) {
  return useQuery({
    queryKey: [
      "map-nearby",
      bounds?.sw.lat,
      bounds?.sw.lng,
      bounds?.ne.lat,
      bounds?.ne.lng,
      category,
    ],
    queryFn: () => getNearby(bounds!, category),
    enabled: bounds != null,
  });
}

export function useRegionLabel(center: LatLng | null, enabled: boolean) {
  return useQuery({
    queryKey: ["region-label", center?.lat, center?.lng],
    queryFn: () => getRegionLabel(center!.lat, center!.lng),
    enabled: enabled && center != null,
  });
}
