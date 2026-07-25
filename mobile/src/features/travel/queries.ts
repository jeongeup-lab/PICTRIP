import { useMutation } from "@tanstack/react-query";
import { askAgent, type AskInput } from "@/features/travel/api";

export function useAskAgentMutation() {
  return useMutation({ mutationFn: (input: AskInput) => askAgent(input) });
}
