import { create } from "zustand";
import type { Plan } from "@/features/plan/api";
import {
  mergeRecent,
  readRecentPlans,
  toRecentPlan,
  writeRecentPlans,
  type RecentPlan,
} from "@/features/plan/lib/recent-plans";

interface RecentPlansState {
  plans: RecentPlan[];
  remember: (plan: Plan) => void;
}

export const useRecentPlans = create<RecentPlansState>((set) => ({
  plans: readRecentPlans(),
  remember: (plan) =>
    set((s) => {
      const entry = toRecentPlan(plan);
      if (!entry) return s;
      const plans = mergeRecent(s.plans, entry);
      writeRecentPlans(plans);
      return { plans };
    }),
}));
