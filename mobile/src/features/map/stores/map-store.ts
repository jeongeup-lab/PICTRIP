import { create } from "zustand";
import { type Bounds, type LatLng, bboxFromCenter } from "@/features/map/lib/geo";
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
  viewportBounds: Bounds | null;
  // The bbox the nearby query fetches. Derived from the anchor center (±RADIUS_M)
  // on GPS/region anchors, or the real visible rectangle when "이 지역에서 검색".
  queryBounds: Bounds | null;
  lastQueryCenter: LatLng | null;
  selectedSpotId: string | null;
  setAnchor: (center: LatLng, source: AnchorSource, gps?: LatLng | null, bounds?: Bounds) => void;
  setLabel: (label: RegionLabel | null) => void;
  setCategory: (c: NearbyCategory | null) => void;
  onViewportChange: (c: LatLng, bounds?: Bounds) => void;
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
  viewportBounds: null,
  queryBounds: null,
  lastQueryCenter: null,
  selectedSpotId: null,
};

/** Single source of truth for the map tab. queryBounds drives the nearby fetch
 * (the bbox the user sees); panning only updates viewportCenter/Bounds so the
 * pill can appear without refetching (S05 §1.3-1.4). */
export const useMapStore = create<MapState>((set, get) => ({
  ...initial,

  setAnchor: (center, source, gps, bounds) =>
    set((s) => ({
      center,
      anchorSource: source,
      gpsCoords: gps !== undefined ? gps : s.gpsCoords,
      lastQueryCenter: center,
      viewportCenter: center,
      // Real viewport bbox if the map reported one (pan→search), else a square
      // ±RADIUS_M box around the new center (GPS/region anchors).
      queryBounds: bounds ?? bboxFromCenter(center, RADIUS_M),
    })),

  setLabel: (label) => set({ label }),
  setCategory: (category) => set({ category }),
  onViewportChange: (viewportCenter, viewportBounds) =>
    set((s) => ({ viewportCenter, viewportBounds: viewportBounds ?? s.viewportBounds })),

  searchHere: () => {
    const { viewportCenter, viewportBounds } = get();
    if (!viewportCenter) return;
    get().setAnchor(viewportCenter, "pan", undefined, viewportBounds ?? undefined);
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
