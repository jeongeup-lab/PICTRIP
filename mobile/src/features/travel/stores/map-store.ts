import { create } from "zustand";
import type { PlacedSpot } from "@/features/travel/lib/spot-geo";

interface TravelMapState {
  spots: PlacedSpot[];
  question: string;
  selectedId: string | null;
  open: (spots: PlacedSpot[], question: string) => void;
  select: (contentId: string) => void;
  clear: () => void;
}

export const useTravelMap = create<TravelMapState>((set) => ({
  spots: [],
  question: "",
  selectedId: null,
  open: (spots, question) => set({ spots, question, selectedId: spots[0]?.spot.contentId ?? null }),
  select: (contentId) => set({ selectedId: contentId }),
  clear: () => set({ spots: [], question: "", selectedId: null }),
}));
