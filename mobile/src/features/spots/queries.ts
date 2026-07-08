import { useQuery } from "@tanstack/react-query";
import { getSpot, getNearby } from "@/features/spots/api";
import { queryClient } from "@/lib/query-client";
import type { NearbySpot, SpotCard, SpotDetail } from "@/lib/api-types";

/** Hero-relevant fields a tapped card hands off so the detail hero (image +
 * title + subline) paints instantly while the cold KTO detail loads. A
 * NearbySpot carries the richer subline (overview / region); a plain SpotCard
 * fills those with null. */
type SpotSeed = SpotCard & Partial<Pick<NearbySpot, "overview" | "regionName" | "sigunguName">>;

/** In-memory handoff from a tapped card to the full `[contentId]` screen, which
 * only receives `contentId` via route params. Written on onPressIn (next to the
 * prefetch), read once by `useSpot` as placeholderData — kept out of route
 * params so navigation stays a plain path push. Session-bounded; soft-capped so
 * a long browsing session can't grow it without bound. */
const seedStash = new Map<string, SpotSeed>();

function stashSeed(seed: SpotSeed) {
  if (seedStash.size > 300) seedStash.clear();
  seedStash.set(seed.contentId, seed);
}

/** Partial SpotDetail from a seed card so the hero renders instantly. Body
 * sections stay skeletoned (isPlaceholderData) until the authoritative row
 * arrives — the snippet overview never flashes as the final text. */
function seedToDetail(seed: SpotSeed | null | undefined): SpotDetail | undefined {
  if (!seed) return undefined;
  return {
    contentId: seed.contentId,
    title: seed.title,
    firstImageUrl: seed.firstImageUrl,
    addr1: seed.addr1 ?? null,
    addr2: null,
    mapx: seed.mapx ?? null,
    mapy: seed.mapy ?? null,
    overview: seed.overview ?? null,
    homepage: null,
    tel: null,
    category: seed.category,
    regionName: seed.regionName ?? null,
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
  });
}

/** Warm the spot-detail cache before navigation (cold detail can take seconds).
 * Passing the card (not just its id) also stashes a hero seed so the next
 * detail screen paints instantly instead of skeletoning. */
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
