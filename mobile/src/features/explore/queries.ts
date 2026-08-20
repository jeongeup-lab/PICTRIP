import { keepPreviousData, useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { getExplore, getMatches } from "@/features/explore/api";
import { queryClient } from "@/lib/query-client";

const MATCHES_STALE = 6 * 60 * 60 * 1000;

function matchesQuery(id: number) {
  return {
    queryKey: ["matches", id],
    queryFn: () => getMatches(id),
    staleTime: MATCHES_STALE,
  };
}

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
  return useQuery({ ...matchesQuery(id), enabled: opts.enabled });
}

export function prefetchMatches(id: number | null | undefined): void {
  if (id == null) return;
  void queryClient.prefetchQuery(matchesQuery(id));
}
