import { keepPreviousData, useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { getMatches, getPosts } from "@/features/feed/posts-api";
import { queryClient } from "@/lib/query-client";

const MATCHES_STALE = 6 * 60 * 60 * 1000;

export function usePostsFeed(seed?: string) {
  return useInfiniteQuery({
    queryKey: ["posts", seed],
    queryFn: ({ pageParam }) => getPosts({ seed, cursor: pageParam ?? undefined, limit: 6 }),
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

export function prefetchMatches(id: number) {
  void queryClient.prefetchQuery({
    queryKey: ["matches", id],
    queryFn: () => getMatches(id),
    staleTime: MATCHES_STALE,
  });
}
