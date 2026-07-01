import { type Bounds } from "@/features/map/lib/geo";

/**
 * The bottom sheet overlays the lower part of the map, so markers/spots under the
 * panel are queried but never visible. `clipBoundsToVisible` raises the south edge
 * of the query bbox to the panel's top edge so the fetch only covers the strip of
 * map the user can actually see above the sheet.
 *
 * `panelTopY` = the current sheet snap translateY (px from the top of the screen);
 * `screenH` = the window height used by the sheet. The visible fraction of the map
 * is `panelTopY / screenH`, measured down from the top (= `ne.lat`).
 */

// Never clip below this: even at the tallest sheet snap keep at least the top 15%
// of the map so a degenerate/empty (or inverted) band is impossible.
const MIN_VISIBLE_FRACTION = 0.15;

export function clipBoundsToVisible(bounds: Bounds, panelTopY: number, screenH: number): Bounds {
  const { sw, ne } = bounds;
  if (!(screenH > 0)) return bounds;

  let fraction = panelTopY / screenH;
  if (!Number.isFinite(fraction) || fraction > 1) fraction = 1;
  if (fraction < MIN_VISIBLE_FRACTION) fraction = MIN_VISIBLE_FRACTION;

  const visibleSouthLat = ne.lat - (ne.lat - sw.lat) * fraction;
  return { sw: { lat: visibleSouthLat, lng: sw.lng }, ne };
}
