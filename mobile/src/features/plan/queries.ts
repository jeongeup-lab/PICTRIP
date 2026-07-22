import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { queryClient } from "@/lib/query-client";
import {
  assemblePlan,
  editPlan,
  getAlternatives,
  getPlan,
  importContent,
  matchPhoto,
  planFromSpot,
  type AssembleBody,
  type Plan,
  type PhotoUpload,
  type PlanEdit,
} from "@/features/plan/api";
import { useRecentPlans } from "@/features/plan/stores/recent-plans-store";

export const planKeys = {
  detail: (planId: string) => ["plan", planId] as const,
  alternatives: (planId: string, day: number, slot: number) =>
    ["plan-alternatives", planId, day, slot] as const,
};

export function cachePlan(plan: Plan): void {
  if (plan.planId) queryClient.setQueryData(planKeys.detail(plan.planId), plan);
}

export function usePlan(planId: string) {
  return useQuery({
    queryKey: planKeys.detail(planId),
    queryFn: () => getPlan(planId),
    staleTime: Infinity,
  });
}

export function usePhotoMatchMutation() {
  return useMutation({ mutationFn: (photo: PhotoUpload) => matchPhoto(photo) });
}

export function useImportMutation() {
  return useMutation({
    mutationFn: (source: { url?: string; text?: string }) => importContent(source),
  });
}

export function usePlanFromSpotMutation() {
  const remember = useRecentPlans((s) => s.remember);
  return useMutation({
    mutationFn: (input: { contentId: string; days: number }) =>
      planFromSpot(input.contentId, input.days),
    onSuccess: (plan) => {
      cachePlan(plan);
      remember(plan);
    },
  });
}

export function useAssembleMutation() {
  const remember = useRecentPlans((s) => s.remember);
  return useMutation({
    mutationFn: (body: AssembleBody) => assemblePlan(body),
    onSuccess: (plan) => {
      cachePlan(plan);
      remember(plan);
    },
  });
}

export function useAlternatives(planId: string, target: { day: number; slot: number } | null) {
  return useQuery({
    queryKey: planKeys.alternatives(planId, target?.day ?? -1, target?.slot ?? -1),
    queryFn: () => getAlternatives(planId, target!.day, target!.slot),
    enabled: target != null,
    staleTime: Infinity,
  });
}

export function usePlanEditMutation(planId: string) {
  const qc = useQueryClient();
  const remember = useRecentPlans((s) => s.remember);
  return useMutation({
    mutationFn: (edit: PlanEdit) => editPlan(planId, edit),
    onSuccess: (plan) => {
      qc.setQueryData(planKeys.detail(planId), plan);
      void qc.invalidateQueries({ queryKey: ["plan-alternatives", planId] });
      remember(plan);
    },
  });
}
