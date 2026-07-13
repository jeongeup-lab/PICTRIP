import { useInfiniteQuery } from "@tanstack/react-query";
import { getExplore } from "@/features/explore/api";

export function useExploreFeed(seed: string | null) {
  return useInfiniteQuery({
    queryKey: ["explore", seed],
    queryFn: ({ pageParam }) =>
      getExplore({ seed: seed ?? undefined, cursor: pageParam ?? undefined, limit: 30 }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => (last.hasMore ? last.nextCursor : undefined),
  });
}
