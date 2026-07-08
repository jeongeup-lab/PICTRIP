import { useQuery } from "@tanstack/react-query";
import { getSpot, getNearby } from "@/features/spots/api";
import { queryClient } from "@/lib/query-client";
import type { NearbySpot, SpotDetail } from "@/lib/api-types";

/** Partial SpotDetail from a map/nearby card so the hero (image + title +
 * subline + lead) renders instantly while the cold KTO detail loads. Body
 * sections stay skeletoned (isPlaceholderData) until the authoritative row
 * arrives — the snippet overview never flashes as the final text. */
function seedFromNearby(seed: NearbySpot | null | undefined): SpotDetail | undefined {
  if (!seed) return undefined;
  return {
    contentId: seed.contentId,
    title: seed.title,
    firstImageUrl: seed.firstImageUrl,
    addr1: seed.addr1 ?? null,
    addr2: null,
    mapx: seed.mapx ?? null,
    mapy: seed.mapy ?? null,
    overview: seed.overview,
    homepage: null,
    tel: null,
    category: seed.category,
    regionName: seed.regionName,
    sigunguName: seed.sigunguName,
    detailStatus: "placeholder",
    images: [],
    intro: null,
  };
}

export function useSpot(contentId: string, seed?: NearbySpot | null) {
  return useQuery({
    queryKey: ["spot", contentId],
    queryFn: () => getSpot(contentId),
    enabled: !!contentId,
    placeholderData: () => seedFromNearby(seed),
  });
}

/** Warm the spot-detail cache before navigation (cold detail can take seconds). */
export function prefetchSpot(contentId: string) {
  if (!contentId) return;
  void queryClient.prefetchQuery({
    queryKey: ["spot", contentId],
    queryFn: () => getSpot(contentId),
  });
}

export function useNearby(lat: number | null, lng: number | null, excludeId: string) {
  return useQuery({
    queryKey: ["nearby", lat, lng],
    queryFn: () => getNearby(lat as number, lng as number),
    enabled: lat != null && lng != null,
    select: (spots) => spots.filter((s) => s.contentId !== excludeId).slice(0, 12),
  });
}
