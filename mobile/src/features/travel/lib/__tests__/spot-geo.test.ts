import { bounds, center, pinsFrom, placed } from "@/features/travel/lib/spot-geo";
import type { TravelSpot } from "@/features/travel/api";

const spot = (over: Partial<TravelSpot> = {}): TravelSpot => ({
  contentId: "c1",
  title: "무릉계곡",
  regionLabel: "제주 제주시",
  imageUrl: null,
  tag: null,
  lat: 33.5,
  lng: 126.5,
  ...over,
});

describe("placed", () => {
  it("keeps only spots the map can actually pin", () => {
    const rows = placed([
      spot({ contentId: "a" }),
      spot({ contentId: "b", lat: null }),
      spot({ contentId: "c", lng: null }),
    ]);

    expect(rows.map((r) => r.spot.contentId)).toEqual(["a"]);
  });
});

describe("pinsFrom", () => {
  it("hands the map lng as mapx and lat as mapy", () => {
    const [pin] = pinsFrom(placed([spot({ lat: 33.5, lng: 126.5 })]));

    expect(pin.mapx).toBe(126.5);
    expect(pin.mapy).toBe(33.5);
    expect(pin.contentId).toBe("c1");
    expect(pin.title).toBe("무릉계곡");
  });

  it("carries the category through so the pin can draw its glyph", () => {
    const [pin] = pinsFrom(placed([spot({ categoryGroup: "cafe" })]));

    expect(pin.categoryGroup).toBe("cafe");
  });

  it("falls back to a plain pin when the server names no category", () => {
    expect(pinsFrom(placed([spot()]))[0].categoryGroup).toBeNull();
  });
});

describe("center", () => {
  it("averages the pinned spots", () => {
    const middle = center(
      placed([
        spot({ contentId: "a", lat: 33.0, lng: 126.0 }),
        spot({ contentId: "b", lat: 34.0, lng: 127.0 }),
      ]),
    );

    expect(middle).toEqual({ lat: 33.5, lng: 126.5 });
  });

  it("is null with nothing to center on", () => {
    expect(center([])).toBeNull();
  });
});

describe("bounds", () => {
  it("spans the corners of every pinned spot", () => {
    const box = bounds(
      placed([
        spot({ contentId: "a", lat: 33.2, lng: 126.2 }),
        spot({ contentId: "b", lat: 33.6, lng: 126.9 }),
      ]),
    );

    expect(box).toEqual({ sw: { lat: 33.2, lng: 126.2 }, ne: { lat: 33.6, lng: 126.9 } });
  });

  it("is null when nothing can be pinned", () => {
    expect(bounds([])).toBeNull();
  });

  it("widens a single spot into a box the map can zoom to", () => {
    const box = bounds(placed([spot({ lat: 33.5, lng: 126.5 })]))!;

    expect(box.ne.lat - box.sw.lat).toBeCloseTo(0.02);
    expect(box.ne.lng - box.sw.lng).toBeCloseTo(0.02);
    expect((box.ne.lat + box.sw.lat) / 2).toBeCloseTo(33.5);
  });
});
