import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { SpotCard } from "@/lib/api-types";
import { useAuthStore } from "@/features/auth/stores/auth-store";
import { listSaved, saveSpot, unsaveSpot } from "@/features/saved/api";
import { containsId, removeById } from "@/features/saved/lib/optimistic";

const savedKeys = { list: ["saved"] as const };

const RECOMMENDATIONS_ROOT = ["home-recommendations"] as const;

export function useSavedList() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  return useQuery({
    queryKey: savedKeys.list,
    queryFn: listSaved,
    enabled: isAuthenticated,
  });
}

export function useIsSaved(contentId: string): boolean {
  const { data } = useSavedList();
  return containsId(data, contentId);
}

export function useSaveMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (contentId: string) => saveSpot(contentId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: savedKeys.list });
      void qc.invalidateQueries({ queryKey: RECOMMENDATIONS_ROOT });
    },
  });
}

export function useUnsaveMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (contentId: string) => unsaveSpot(contentId),
    onMutate: async (contentId: string) => {
      await qc.cancelQueries({ queryKey: savedKeys.list });
      const prev = qc.getQueryData<SpotCard[]>(savedKeys.list);
      if (prev) qc.setQueryData<SpotCard[]>(savedKeys.list, removeById(prev, contentId));
      return { prev };
    },
    onError: (_e, _id, ctx) => {
      if (ctx?.prev) qc.setQueryData(savedKeys.list, ctx.prev);
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: savedKeys.list });
      void qc.invalidateQueries({ queryKey: RECOMMENDATIONS_ROOT });
    },
  });
}
