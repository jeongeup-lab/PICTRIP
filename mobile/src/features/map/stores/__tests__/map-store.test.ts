import { useMapStore } from "@/features/map/stores/map-store";

const seoul = { lat: 37.5666, lng: 126.9784 };

describe("map-store", () => {
  beforeEach(() => useMapStore.getState().reset());

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
    useMapStore.getState().onViewportChange({ lat: 37.58, lng: 126.9784 });
    expect(useMapStore.getState().pillVisible()).toBe(true);
    expect(useMapStore.getState().center).toEqual(seoul);
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

  it("GPS anchor queryBounds contains the anchor center", () => {
    useMapStore.getState().setAnchor(seoul, "gps", seoul);
    const qb = useMapStore.getState().queryBounds!;
    expect(qb.sw.lat).toBeLessThan(seoul.lat);
    expect(qb.ne.lat).toBeGreaterThan(seoul.lat);
  });

  it("searchHere clips the real viewport bbox south edge to the sheet top", () => {
    const vpBounds = { sw: { lat: 37.5, lng: 126.9 }, ne: { lat: 37.66, lng: 127.05 } };
    useMapStore.getState().setAnchor(seoul, "gps", seoul);
    useMapStore.getState().onViewportChange({ lat: 37.58, lng: 126.9784 }, vpBounds);
    useMapStore.getState().searchHere();
    const qb = useMapStore.getState().queryBounds!;
    expect(qb.ne).toEqual(vpBounds.ne);
    expect(qb.sw.lng).toBe(vpBounds.sw.lng);
    expect(qb.sw.lat).toBeGreaterThan(vpBounds.sw.lat);
  });

  it("setSnap keeps the pan-search queryBounds frozen (results stay put while dragging)", () => {
    const vpBounds = { sw: { lat: 37.5, lng: 126.9 }, ne: { lat: 37.66, lng: 127.05 } };
    useMapStore.getState().setAnchor(seoul, "gps", seoul);
    useMapStore.getState().onViewportChange({ lat: 37.58, lng: 126.9784 }, vpBounds);
    useMapStore.getState().searchHere();
    const before = useMapStore.getState().queryBounds;
    useMapStore.getState().setSnap("peek");
    expect(useMapStore.getState().queryBounds).toEqual(before);
    useMapStore.getState().setSnap("full");
    expect(useMapStore.getState().queryBounds).toEqual(before);
  });

  it("setSnap leaves a center-derived queryBounds unchanged", () => {
    useMapStore.getState().setAnchor(seoul, "gps", seoul);
    const before = useMapStore.getState().queryBounds;
    useMapStore.getState().setSnap("peek");
    expect(useMapStore.getState().queryBounds).toEqual(before);
  });

  it("a new anchor closes an open spot-detail selection", () => {
    useMapStore.getState().setAnchor(seoul, "gps", seoul);
    useMapStore.getState().selectSpot("12345");
    useMapStore.getState().applyRegion({ lat: 35.1, lng: 129.0 });
    expect(useMapStore.getState().selectedSpotId).toBeNull();
  });

  it("setGpsCoords fills the blue-dot coords without moving the anchor", () => {
    useMapStore.getState().setAnchor(seoul, "pan", null);
    useMapStore.getState().setGpsCoords({ lat: 35.1, lng: 129.0 });
    const s = useMapStore.getState();
    expect(s.gpsCoords).toEqual({ lat: 35.1, lng: 129.0 });
    expect(s.center).toEqual(seoul);
    expect(s.anchorSource).toBe("pan");
  });
});
