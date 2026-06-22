import { useQuery } from "@tanstack/react-query";
import { getHomeFeed } from "@/features/feed/api";

export function useHomeFeed() {
  return useQuery({ queryKey: ["home-feed"], queryFn: getHomeFeed });
}
