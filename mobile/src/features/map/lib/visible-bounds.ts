import { type Bounds } from "@/features/map/lib/geo";

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
