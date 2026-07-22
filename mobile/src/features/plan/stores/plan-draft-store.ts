import { create } from "zustand";
import type { ImportResult, PhotoMatch, PhotoUpload } from "@/features/plan/api";
import { defaultSelection, requestedDays, toggleIndex } from "@/features/plan/lib/place-selection";

interface PlanDraftState {
  photo: PhotoUpload | null;
  matches: PhotoMatch[];
  seedIndex: number | null;
  imported: ImportResult | null;
  sourceUrl: string | null;
  selected: number[];
  days: number | null;
  missingOpen: boolean;
  startPhotoFlow: (photo: PhotoUpload) => void;
  setMatches: (matches: PhotoMatch[]) => void;
  selectSeed: (index: number) => void;
  startImportFlow: (imported: ImportResult, sourceUrl: string | null) => void;
  toggleSelected: (index: number) => void;
  toggleMissing: () => void;
}

export const usePlanDraft = create<PlanDraftState>((set) => ({
  photo: null,
  matches: [],
  seedIndex: null,
  imported: null,
  sourceUrl: null,
  selected: [],
  days: null,
  missingOpen: false,
  startPhotoFlow: (photo) => set({ photo, matches: [], seedIndex: null }),
  setMatches: (matches) => set({ matches }),
  selectSeed: (index) => set({ seedIndex: index }),
  startImportFlow: (imported, sourceUrl) =>
    set({
      imported,
      sourceUrl,
      selected: defaultSelection(imported.places),
      days: requestedDays(imported.tripDays),
      missingOpen: false,
    }),
  toggleSelected: (index) => set((s) => ({ selected: toggleIndex(s.selected, index) })),
  toggleMissing: () => set((s) => ({ missingOpen: !s.missingOpen })),
}));
