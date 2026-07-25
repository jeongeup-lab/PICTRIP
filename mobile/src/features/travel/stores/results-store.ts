import { create } from "zustand";
import type { TravelSpot } from "@/features/travel/api";

interface ResultsState {
  title: string;
  spots: TravelSpot[];
  open: (title: string, spots: TravelSpot[]) => void;
}

export const useResults = create<ResultsState>((set) => ({
  title: "",
  spots: [],
  open: (title, spots) => set({ title, spots }),
}));
