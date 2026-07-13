import { keepPreviousData, useInfiniteQuery } from "@tanstack/react-query";
import { getExplore } from "@/features/explore/api";

export function useExploreFeed(seed: string) {
  return useInfiniteQuery({
    queryKey: ["explore", seed],
    queryFn: ({ pageParam }) => getExplore({ seed, cursor: pageParam ?? undefined, limit: 30 }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => (last.hasMore ? last.nextCursor : undefined),
    placeholderData: keepPreviousData,
  });
}
