import { keepPreviousData, useInfiniteQuery } from "@tanstack/react-query";
import { getShorts } from "@/features/shorts/api";

export function useShortsFeed() {
  return useInfiniteQuery({
    queryKey: ["shorts"],
    queryFn: ({ pageParam }) => getShorts({ cursor: pageParam ?? undefined, limit: 6 }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => (last.hasMore ? last.nextCursor : undefined),
    placeholderData: keepPreviousData,
    staleTime: 10 * 60 * 1000,
  });
}
