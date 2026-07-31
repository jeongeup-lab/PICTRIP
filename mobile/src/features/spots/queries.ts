import { useQuery } from "@tanstack/react-query";
import { getSpot, getNearby } from "@/features/spots/api";
import { queryClient } from "@/lib/query-client";
import type { SpotDetail } from "@/lib/api-types";

interface SpotSeed {
  contentId: string;
  title: string;
  firstImageUrl?: string | null;
  imageUrl?: string | null;
  addr1?: string | null;
  mapx?: number | null;
  mapy?: number | null;
  lng?: number | null;
  lat?: number | null;
  category?: string | null;
  overview?: string | null;
  overviewFirst?: string | null;
  regionName?: string | null;
  sigunguName?: string | null;
  regionLabel?: string | null;
}

const seedStash = new Map<string, SpotSeed>();

function stashSeed(seed: SpotSeed) {
  if (seedStash.size > 300) seedStash.clear();
  seedStash.set(seed.contentId, seed);
}

function seedToDetail(seed: SpotSeed | null | undefined): SpotDetail | undefined {
  if (!seed) return undefined;
  return {
    contentId: seed.contentId,
    title: seed.title,
    firstImageUrl: seed.firstImageUrl ?? seed.imageUrl ?? null,
    addr1: seed.addr1 ?? null,
    addr2: null,
    mapx: seed.mapx ?? seed.lng ?? null,
    mapy: seed.mapy ?? seed.lat ?? null,
    overview: seed.overview ?? seed.overviewFirst ?? null,
    homepage: null,
    tel: null,
    category: seed.category ?? null,
    regionName: seed.regionName ?? seed.regionLabel ?? null,
    sigunguName: seed.sigunguName ?? null,
    detailStatus: "placeholder",
    images: [],
    intro: null,
  };
}

export function useSpot(contentId: string, seed?: SpotSeed | null) {
  const resolved = seed ?? seedStash.get(contentId) ?? null;
  return useQuery({
    queryKey: ["spot", contentId],
    queryFn: () => getSpot(contentId),
    enabled: !!contentId,
    placeholderData: () => seedToDetail(resolved),
    refetchInterval: (query) => {
      const status = query.state.data?.detailStatus;
      if (status === "pending") return 1500;
      if (status === "unavailable") return 60_000;
      return false;
    },
  });
}

export function prefetchSpot(spot: SpotSeed | string) {
  const contentId = typeof spot === "string" ? spot : spot.contentId;
  if (!contentId) return;
  if (typeof spot !== "string") stashSeed(spot);
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
