import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/features/auth/stores/auth-store";
import {
  getNearby,
  getRecommendations,
  getRegionLabel,
  getTastePicks,
  getTrending,
} from "@/features/home/api";
import type { TasteCategory } from "@/features/home/api";
import type { Coords } from "@/features/map/usecases/request-location";

const NEARBY_STALE_MS = 5 * 60 * 1000;
const TRENDING_STALE_MS = 10 * 60 * 1000;

function coordKey(coords: Coords | null): [number, number] | null {
  return coords ? [Math.round(coords.lat * 1000), Math.round(coords.lng * 1000)] : null;
}

export const homeKeys = {
  nearby: (coords: Coords | null) => ["home-nearby", coordKey(coords)] as const,
  trending: ["home-trending"] as const,
  region: (coords: Coords | null) => ["home-region", coordKey(coords)] as const,
  tastePicks: ["home-taste-picks"] as const,
  recommendationsRoot: ["home-recommendations"] as const,
  recommendations: (userId: number | null, coords: Coords | null) =>
    ["home-recommendations", userId, coordKey(coords)] as const,
};

export function useNearby(coords: Coords | null) {
  return useQuery({
    queryKey: homeKeys.nearby(coords),
    queryFn: () => getNearby(coords as Coords),
    enabled: !!coords,
    staleTime: NEARBY_STALE_MS,
  });
}

export function useTrending() {
  return useQuery({
    queryKey: homeKeys.trending,
    queryFn: () => getTrending(),
    staleTime: TRENDING_STALE_MS,
  });
}

export function useRegionLabel(coords: Coords | null) {
  return useQuery({
    queryKey: homeKeys.region(coords),
    queryFn: () => getRegionLabel(coords as Coords),
    enabled: !!coords,
    staleTime: TRENDING_STALE_MS,
  });
}

export function useTastePicks(limit: number, category?: TasteCategory) {
  return useQuery({
    queryKey: [...homeKeys.tastePicks, limit, category ?? "all"],
    queryFn: () => getTastePicks(limit, category),
    staleTime: TRENDING_STALE_MS,
  });
}

export function useRecommendations(coords: Coords | null) {
  const userId = useAuthStore((s) => s.user?.id ?? null);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  return useQuery({
    queryKey: homeKeys.recommendations(userId, coords),
    queryFn: () => getRecommendations(coords ?? undefined),
    enabled: isAuthenticated && userId !== null,
    staleTime: NEARBY_STALE_MS,
  });
}
