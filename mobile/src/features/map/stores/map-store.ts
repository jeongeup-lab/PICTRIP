import { create } from "zustand";
import { type Bounds, type LatLng, bboxFromCenter } from "@/features/map/lib/geo";
import { clipBoundsToVisible } from "@/features/map/lib/visible-bounds";
import type { AnchorSource } from "@/features/map/lib/region-label";
import type { NearbyCategory } from "@/features/map/lib/nearby-categories";
import type { RegionLabel } from "@/lib/api-types";
import { shouldShowSearchHere } from "@/features/map/lib/search-here";
import { SHEET_SNAP_Y, H as SCREEN_H } from "@/features/map/components/MapBottomSheet";
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
  // Frozen at search time: snap/layout changes never re-derive it, so the
  // fetched result set stays put while the user drags the sheet.
  queryBounds: Bounds | null;
  // Map view height in px (window minus tab bar) — the denominator of the
  // visible-fraction clip. Set from the map screen's onLayout; the window
  // height alone over-clips because the tab bar shortens the map view.
  mapViewH: number;
  lastQueryCenter: LatLng | null;
  selectedSpotId: string | null;
  setAnchor: (center: LatLng, source: AnchorSource, gps?: LatLng | null, bounds?: Bounds) => void;
  setLabel: (label: RegionLabel | null) => void;
  setCategory: (c: NearbyCategory | null) => void;
  setGpsCoords: (c: LatLng) => void;
  setMapViewH: (h: number) => void;
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
  mapViewH: SCREEN_H,
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
      // A new anchor is a new search context: close an open spot-detail panel
      // (e.g. region applied from the header while the panel covered the list).
      selectedSpotId: null,
      // Pan→search passes the real viewport bbox: clip its south edge to the
      // sheet top so we never query (and pin) spots the panel hides. GPS/region
      // anchors get a ±RADIUS_M square around the center — NOT screen-aligned,
      // so clipping it by a screen fraction would cut a distance band that can
      // exclude even the anchor itself; query it unclipped.
      queryBounds: bounds
        ? clipBoundsToVisible(bounds, SHEET_SNAP_Y[s.snap], s.mapViewH)
        : bboxFromCenter(center, RADIUS_M),
    })),

  setLabel: (label) => set({ label }),
  setCategory: (category) => set({ category }),
  setGpsCoords: (gpsCoords) => set({ gpsCoords }),
  setMapViewH: (mapViewH) => set({ mapViewH }),
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

  // Snap changes never touch queryBounds: re-clipping on every drag refetched
  // a different distance-capped result set, shuffling the list mid-gesture.
  // The strip a lower snap reveals stays unqueried until the next search.
  setSnap: (snap) => set({ snap }),
  selectSpot: (selectedSpotId) => set({ selectedSpotId }),

  pillVisible: () => shouldShowSearchHere(get().viewportCenter, get().lastQueryCenter, RADIUS_M),

  reset: () => set({ ...initial }),
}));
