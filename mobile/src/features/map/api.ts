import { api } from "@/lib/api-client";
import type { NearbySpot, RegionLabel, RegionNode } from "@/lib/api-types";
import type { Bounds } from "@/features/map/lib/geo";
import type { NearbyCategory } from "@/features/map/lib/nearby-categories";

/** Nearby spots inside the visible map bbox (server sorts by distance asc +
 * caps). 전체 = omit category. api-client unwraps JSend once. */
export async function getNearby(
  bounds: Bounds,
  category?: NearbyCategory | null,
): Promise<NearbySpot[]> {
  return (await api.get("/map/nearby", {
    params: {
      sw_lat: bounds.sw.lat,
      sw_lng: bounds.sw.lng,
      ne_lat: bounds.ne.lat,
      ne_lng: bounds.ne.lng,
      category: category ?? undefined,
    },
  })) as unknown as NearbySpot[];
}

/** Reverse-geocoded region label for the header (Kakao coord2regioncode). */
export async function getRegionLabel(lat: number, lng: number): Promise<RegionLabel> {
  return (await api.get("/map/region", { params: { lat, lng } })) as unknown as RegionLabel;
}

/** 17 시도 → 시군구 tree with runtime-AVG centroids (static; cache-friendly). */
export async function getRegionsTree(): Promise<RegionNode[]> {
  return (await api.get("/map/regions-tree")) as unknown as RegionNode[];
}
