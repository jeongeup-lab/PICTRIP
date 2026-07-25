import { create } from "zustand";
import { DEFAULT_CONDITIONS, type Conditions } from "@/features/travel/api";

interface ConditionsState {
  conditions: Conditions;
  apply: (next: Conditions) => void;
  reset: () => void;
}

export const useConditions = create<ConditionsState>((set) => ({
  conditions: DEFAULT_CONDITIONS,
  apply: (next) => set({ conditions: next }),
  reset: () => set({ conditions: DEFAULT_CONDITIONS }),
}));
