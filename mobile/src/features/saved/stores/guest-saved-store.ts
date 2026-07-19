import { create } from "zustand";
import type { SpotCard } from "@/lib/api-types";
import { containsId, removeById } from "@/features/saved/lib/optimistic";
import { readGuestSaved, writeGuestSaved } from "@/features/saved/lib/guest-storage";

interface GuestSavedState {
  items: SpotCard[];
  hydrated: boolean;
  hydrate: () => Promise<void>;
  toggle: (spot: SpotCard) => void;
  remove: (contentId: string) => void;
  clear: () => void;
}

export const useGuestSavedStore = create<GuestSavedState>((set, get) => ({
  items: [],
  hydrated: false,

  hydrate: async () => {
    const items = await readGuestSaved();
    set({ items, hydrated: true });
  },

  toggle: (spot) => {
    const next = containsId(get().items, spot.contentId)
      ? removeById(get().items, spot.contentId)
      : [spot, ...get().items];
    set({ items: next });
    void writeGuestSaved(next);
  },

  remove: (contentId) => {
    const next = removeById(get().items, contentId);
    set({ items: next });
    void writeGuestSaved(next);
  },

  clear: () => {
    set({ items: [] });
    void writeGuestSaved([]);
  },
}));

void useGuestSavedStore.getState().hydrate();
