import { useMapStore } from "@/features/map/stores/map-store";
import { bboxFromCenter } from "@/features/map/lib/geo";
import { RADIUS_M } from "@/constants/map";

const seoul = { lat: 37.5666, lng: 126.9784 };

describe("map-store", () => {
  beforeEach(() => useMapStore.getState().reset());

  it("GPS/region anchor keeps the user centered in the ±radius query box (not clipped north)", () => {
    // Regression: the synthetic ±RADIUS_M box is centered on the user, so it must
    // NOT be run through clipBoundsToVisible (that would push the south edge north
    // of the user and drop the nearest/southern spots on the default nearby load).
    useMapStore.getState().setAnchor(seoul, "gps", seoul);
    const qb = useMapStore.getState().queryBounds!;
    expect(qb).toEqual(bboxFromCenter(seoul, RADIUS_M));
    expect(qb.sw.lat).toBeLessThan(seoul.lat); // user is inside the box…
    expect(qb.ne.lat).toBeGreaterThan(seoul.lat);
    expect(qb.ne.lat - seoul.lat).toBeCloseTo(seoul.lat - qb.sw.lat, 9); // …and symmetric
  });

  it("pan→search DOES clip the real viewport bbox south edge to the sheet top", () => {
    const vp = { lat: 37.58, lng: 126.9784 };
    const bounds = { sw: { lat: 37.55, lng: 126.95 }, ne: { lat: 37.61, lng: 127.0 } };
    useMapStore.getState().setAnchor(seoul, "gps", seoul);
    useMapStore.getState().onViewportChange(vp, bounds);
    useMapStore.getState().searchHere();
    const qb = useMapStore.getState().queryBounds!;
    expect(qb.sw.lat).toBeGreaterThan(bounds.sw.lat); // south edge raised (panel-hidden strip excluded)
    expect(qb.ne.lat).toBe(bounds.ne.lat); // north edge untouched
  });

  it("setAnchor sets center, source, and lastQueryCenter; pill hidden", () => {
    useMapStore.getState().setAnchor(seoul, "gps", seoul);
    const s = useMapStore.getState();
    expect(s.center).toEqual(seoul);
    expect(s.anchorSource).toBe("gps");
    expect(s.gpsCoords).toEqual(seoul);
    expect(s.lastQueryCenter).toEqual(seoul);
    expect(s.pillVisible()).toBe(false);
  });

  it("onViewportChange beyond threshold makes the pill visible without moving center", () => {
    useMapStore.getState().setAnchor(seoul, "gps", seoul);
    useMapStore.getState().onViewportChange({ lat: 37.58, lng: 126.9784 }); // ~1.5km north
    expect(useMapStore.getState().pillVisible()).toBe(true);
    expect(useMapStore.getState().center).toEqual(seoul); // unchanged
  });

  it("searchHere promotes the viewport to center with source=pan and hides the pill", () => {
    useMapStore.getState().setAnchor(seoul, "gps", seoul);
    const vp = { lat: 37.58, lng: 126.9784 };
    useMapStore.getState().onViewportChange(vp);
    useMapStore.getState().searchHere();
    const s = useMapStore.getState();
    expect(s.center).toEqual(vp);
    expect(s.anchorSource).toBe("pan");
    expect(s.pillVisible()).toBe(false);
  });

  it("applyRegion centers on the centroid with source=region", () => {
    const c = { lat: 35.1, lng: 129.0 };
    useMapStore.getState().applyRegion(c);
    expect(useMapStore.getState().center).toEqual(c);
    expect(useMapStore.getState().anchorSource).toBe("region");
  });

  it("recenterToGps returns to gps coords with source=gps", () => {
    useMapStore.getState().setAnchor(seoul, "gps", seoul);
    useMapStore.getState().applyRegion({ lat: 35, lng: 129 });
    useMapStore.getState().recenterToGps();
    const s = useMapStore.getState();
    expect(s.center).toEqual(seoul);
    expect(s.anchorSource).toBe("gps");
  });

  it("recenterToGps is a no-op when there is no gps fix", () => {
    useMapStore.getState().applyRegion({ lat: 35, lng: 129 });
    useMapStore.getState().recenterToGps();
    expect(useMapStore.getState().anchorSource).toBe("region");
  });

  it("setCategory changes category without moving center", () => {
    useMapStore.getState().setAnchor(seoul, "gps", seoul);
    useMapStore.getState().setCategory("cafe");
    expect(useMapStore.getState().category).toBe("cafe");
    expect(useMapStore.getState().center).toEqual(seoul);
  });
});
