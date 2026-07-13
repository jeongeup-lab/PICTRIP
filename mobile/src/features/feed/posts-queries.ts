import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { getMatches, getPosts } from "@/features/feed/posts-api";

export function usePostsFeed(seed?: string) {
  return useInfiniteQuery({
    queryKey: ["posts", seed],
    queryFn: ({ pageParam }) => getPosts({ seed, cursor: pageParam ?? undefined, limit: 6 }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => (last.hasMore ? last.nextCursor : undefined),
  });
}

export function useMatches(id: number, opts: { enabled: boolean }) {
  return useQuery({
    queryKey: ["matches", id],
    queryFn: () => getMatches(id),
    enabled: opts.enabled,
    staleTime: 6 * 60 * 60 * 1000,
  });
}
