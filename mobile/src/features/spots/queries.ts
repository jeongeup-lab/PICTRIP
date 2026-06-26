import { useQuery } from "@tanstack/react-query";
import { getSpot, getNearby } from "@/features/spots/api";
import { queryClient } from "@/lib/query-client";

export function useSpot(contentId: string) {
  return useQuery({
    queryKey: ["spot", contentId],
    queryFn: () => getSpot(contentId),
    enabled: !!contentId,
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
