import { create } from "zustand";
import { pushRecent } from "@/features/spots/lib/recent-spots";
import type { SpotCard } from "@/lib/api-types";

interface RecentState {
  spots: SpotCard[];
  record: (spot: SpotCard) => void;
  clear: () => void;
}

export const useRecentSpots = create<RecentState>((set) => ({
  spots: [],
  record: (spot) => set((s) => ({ spots: pushRecent(s.spots, spot) })),
  clear: () => set({ spots: [] }),
}));
