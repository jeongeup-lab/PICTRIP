import { create } from "zustand";
import { AppError, type ErrorCode } from "@/lib/app-error";
import type { PhotoSearchResult } from "@/lib/api-types";
import type { PickedImage } from "@/features/photo/usecases/pick-image";
import { getLastKnownCoords } from "@/features/photo/usecases/get-last-known-coords";
import { photoSearch } from "@/features/photo/api";

type Status = "idle" | "loading" | "success" | "error";

interface PhotoFlowState {
  asset: PickedImage | null;
  status: Status;
  result: PhotoSearchResult | null;
  errorCode: ErrorCode | null;
  controller: AbortController | null;
  setAsset: (asset: PickedImage) => void;
  clearAsset: () => void;
  startSearch: () => Promise<void>;
  abort: () => void;
  reset: () => void;
}

/** Ephemeral flow state. NOT TanStack — results are non-cacheable and the image
 * lives only in memory, released on reset() (KTO). Owns the request lifecycle so
 * it survives the 08→09 navigation and supports abort/retry from 09. */
export const usePhotoFlowStore = create<PhotoFlowState>((set, get) => ({
  asset: null,
  status: "idle",
  result: null,
  errorCode: null,
  controller: null,

  setAsset: (asset) => set({ asset }),
  clearAsset: () => set({ asset: null }),

  startSearch: async () => {
    const { asset } = get();
    if (!asset) return;
    get().controller?.abort();
    const controller = new AbortController();
    set({ status: "loading", result: null, errorCode: null, controller });
    try {
      const coords = await getLastKnownCoords();
      const result = await photoSearch(asset, coords, controller.signal);
      if (controller.signal.aborted) return;
      set({ status: "success", result, controller: null });
    } catch (e) {
      if (controller.signal.aborted) return;
      set({
        status: "error",
        errorCode: e instanceof AppError ? e.code : "UNKNOWN",
        controller: null,
      });
    }
  },

  abort: () => {
    get().controller?.abort();
    set({ status: "idle", controller: null });
  },

  reset: () =>
    set({ asset: null, status: "idle", result: null, errorCode: null, controller: null }),
}));
