import { create } from "zustand";
import type { LatLng } from "@/features/map/lib/geo";
import type { AnchorSource } from "@/features/map/lib/region-label";
import type { NearbyCategory } from "@/features/map/lib/nearby-categories";
import type { RegionLabel } from "@/lib/api-types";
import { shouldShowSearchHere } from "@/features/map/lib/search-here";
import { RADIUS_M } from "@/constants/map";

type Snap = "peek" | "half" | "full";

interface MapState {
  center: LatLng | null;
  anchorSource: AnchorSource;
  category: NearbyCategory | null;
  gpsCoords: LatLng | null;
  label: RegionLabel | null;
  snap: Snap;
  viewportCenter: LatLng | null;
  lastQueryCenter: LatLng | null;
  selectedSpotId: string | null;
  setAnchor: (center: LatLng, source: AnchorSource, gps?: LatLng | null) => void;
  setLabel: (label: RegionLabel | null) => void;
  setCategory: (c: NearbyCategory | null) => void;
  onViewportChange: (c: LatLng) => void;
  searchHere: () => void;
  recenterToGps: () => void;
  applyRegion: (centroid: LatLng) => void;
  setSnap: (s: Snap) => void;
  selectSpot: (id: string | null) => void;
  pillVisible: () => boolean;
  reset: () => void;
}

const initial = {
  center: null,
  anchorSource: "gps" as AnchorSource,
  category: null,
  gpsCoords: null,
  label: null,
  snap: "half" as Snap,
  viewportCenter: null,
  lastQueryCenter: null,
  selectedSpotId: null,
};

/** Single source of truth for the map tab. Center/anchor drive the nearby
 * fetch (queries read center+category); panning only updates viewportCenter so
 * the pill can appear without refetching (S05 §1.3-1.4). */
export const useMapStore = create<MapState>((set, get) => ({
  ...initial,

  setAnchor: (center, source, gps) =>
    set((s) => ({
      center,
      anchorSource: source,
      gpsCoords: gps !== undefined ? gps : s.gpsCoords,
      lastQueryCenter: center,
      viewportCenter: center,
    })),

  setLabel: (label) => set({ label }),
  setCategory: (category) => set({ category }),
  onViewportChange: (viewportCenter) => set({ viewportCenter }),

  searchHere: () => {
    const vp = get().viewportCenter;
    if (!vp) return;
    get().setAnchor(vp, "pan");
  },

  recenterToGps: () => {
    const gps = get().gpsCoords;
    if (!gps) return;
    get().setAnchor(gps, "gps", gps);
  },

  applyRegion: (centroid) => get().setAnchor(centroid, "region"),

  setSnap: (snap) => set({ snap }),
  selectSpot: (selectedSpotId) => set({ selectedSpotId }),

  pillVisible: () => shouldShowSearchHere(get().viewportCenter, get().lastQueryCenter, RADIUS_M),

  reset: () => set({ ...initial }),
}));
