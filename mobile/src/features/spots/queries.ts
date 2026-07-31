import { useState } from "react";
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

interface StashedSeed {
  seed: SpotSeed;
  expiresAt: number;
}

const seedStash = new Map<string, StashedSeed>();
const SEED_STASH_TTL_MS = 30_000;
const PENDING_REFETCH_INTERVAL_MS = 750;

function stashSeed(seed: SpotSeed) {
  if (seedStash.size > 300) seedStash.clear();
  seedStash.set(seed.contentId, {
    seed,
    expiresAt: Date.now() + SEED_STASH_TTL_MS,
  });
}

function activeSeed(contentId: string): SpotSeed | null {
  const stashed = seedStash.get(contentId);
  if (!stashed || stashed.expiresAt < Date.now()) return null;
  return stashed.seed;
}

function seedImageUrl(seed: SpotSeed | null | undefined): string | null {
  return seed?.imageUrl ?? seed?.firstImageUrl ?? null;
}

function seedToDetail(seed: SpotSeed | null | undefined): SpotDetail | undefined {
  if (!seed) return undefined;
  return {
    contentId: seed.contentId,
    title: seed.title,
    firstImageUrl: seedImageUrl(seed),
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
  const [stashedSeed] = useState(() => activeSeed(contentId));
  const resolved = seed ?? (stashedSeed?.contentId === contentId ? stashedSeed : null);
  const preferredImageUrl = seedImageUrl(resolved);
  return useQuery({
    queryKey: ["spot", contentId],
    queryFn: () => getSpot(contentId),
    enabled: !!contentId,
    placeholderData: () => seedToDetail(resolved),
    select: (detail) =>
      preferredImageUrl && detail.firstImageUrl !== preferredImageUrl
        ? { ...detail, firstImageUrl: preferredImageUrl }
        : detail,
    refetchInterval: (query) => {
      const status = query.state.data?.detailStatus;
      if (status === "pending") return PENDING_REFETCH_INTERVAL_MS;
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
