import { create } from "zustand";
import type { TravelSpot } from "@/features/travel/api";

interface AnchorState {
  spot: TravelSpot | null;
  pick: (spot: TravelSpot) => void;
  clear: () => void;
}

export const useTravelAnchor = create<AnchorState>((set) => ({
  spot: null,
  pick: (spot) => set({ spot }),
  clear: () => set({ spot: null }),
}));
