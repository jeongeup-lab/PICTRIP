import { useMutation, useQuery } from "@tanstack/react-query";
import { askAgent, fetchMoodImages, type AskInput } from "@/features/travel/api";

export const MOOD_IMAGES_KEY = ["travel", "mood-images"] as const;

export function useAskAgentMutation() {
  return useMutation({ mutationFn: (input: AskInput) => askAgent(input) });
}

export function useMoodImagesQuery(enabled: boolean) {
  return useQuery({
    queryKey: MOOD_IMAGES_KEY,
    queryFn: fetchMoodImages,
    enabled,
    staleTime: 10 * 60 * 1000,
    retry: 1,
  });
}
