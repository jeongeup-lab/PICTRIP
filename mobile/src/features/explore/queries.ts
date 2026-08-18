import { keepPreviousData, useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { getExplore, getMatches } from "@/features/explore/api";

const MATCHES_STALE = 6 * 60 * 60 * 1000;

export function useExploreFeed(seed: string) {
  return useInfiniteQuery({
    queryKey: ["explore", seed],
    queryFn: ({ pageParam }) => getExplore({ seed, cursor: pageParam ?? undefined, limit: 30 }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => (last.hasMore ? last.nextCursor : undefined),
    placeholderData: keepPreviousData,
  });
}

export function useMatches(id: number, opts: { enabled: boolean }) {
  return useQuery({
    queryKey: ["matches", id],
    queryFn: () => getMatches(id),
    enabled: opts.enabled,
    staleTime: MATCHES_STALE,
  });
}
