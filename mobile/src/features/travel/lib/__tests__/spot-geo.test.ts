import {
  bounds,
  center,
  miniFitSpots,
  pinsFrom,
  placed,
  regionGroups,
  spatialSummary,
  spreadKm,
  summaryLine,
} from "@/features/travel/lib/spot-geo";
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
});

describe("miniFitSpots", () => {
  it("frames every spot when they fit the mini map", () => {
    const rows = placed([
      spot({ contentId: "a", regionLabel: "충남 태안군", lat: 36.5, lng: 126.3 }),
      spot({ contentId: "b", regionLabel: "부산 해운대구", lat: 35.16, lng: 129.16 }),
    ]);

    expect(miniFitSpots(rows)).toEqual(rows);
  });

  it("falls back to the busiest area when the results span the country", () => {
    const rows = placed([
      spot({ contentId: "a", regionLabel: "강원 고성군", lat: 38.4, lng: 128.46 }),
      spot({ contentId: "b", regionLabel: "강원 고성군", lat: 38.35, lng: 128.47 }),
      spot({ contentId: "c", regionLabel: "제주 제주시", lat: 33.5, lng: 126.5 }),
    ]);

    expect(miniFitSpots(rows).map((r) => r.spot.contentId)).toEqual(["a", "b"]);
  });

  it("has nothing to frame for an empty answer", () => {
    expect(miniFitSpots([])).toEqual([]);
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

describe("spreadKm", () => {
  it("reports the widest pair, not the first pair", () => {
    const rows = placed([
      spot({ contentId: "a", lat: 33.5, lng: 126.5 }),
      spot({ contentId: "b", lat: 33.51, lng: 126.51 }),
      spot({ contentId: "c", lat: 34.5, lng: 126.5 }),
    ]);

    expect(Math.round(spreadKm(rows))).toBe(111);
  });

  it("is zero for a single spot", () => {
    expect(spreadKm(placed([spot()]))).toBe(0);
  });
});

describe("regionGroups", () => {
  it("groups by the narrowest part of the region label, busiest first", () => {
    const groups = regionGroups(
      placed([
        spot({ contentId: "a", regionLabel: "제주 제주시" }),
        spot({ contentId: "b", regionLabel: "제주 서귀포시" }),
        spot({ contentId: "c", regionLabel: "제주 제주시" }),
      ]),
    );

    expect(groups).toEqual([
      { label: "제주시", count: 2 },
      { label: "서귀포시", count: 1 },
    ]);
  });
});

describe("spatialSummary", () => {
  it("says nothing when there is nothing spatial to say", () => {
    expect(spatialSummary(placed([spot()]))).toBeNull();
    expect(spatialSummary([])).toBeNull();
  });

  it("calls out a single area", () => {
    const summary = spatialSummary(
      placed([
        spot({ contentId: "a", regionLabel: "제주 제주시", lat: 33.5, lng: 126.5 }),
        spot({ contentId: "b", regionLabel: "제주 제주시", lat: 33.51, lng: 126.51 }),
      ]),
    );

    expect(summary).toEqual({ places: "모두 제주시", spread: null });
  });

  it("names two areas with their counts", () => {
    const summary = spatialSummary(
      placed([
        spot({ contentId: "a", regionLabel: "제주 제주시", lat: 33.5, lng: 126.5 }),
        spot({ contentId: "b", regionLabel: "제주 제주시", lat: 33.51, lng: 126.52 }),
        spot({ contentId: "c", regionLabel: "제주 서귀포시", lat: 33.25, lng: 126.56 }),
      ]),
    );

    expect(summary).toEqual({ places: "제주시 2곳 · 서귀포시 1곳", spread: "최대 29km" });
    expect(summaryLine(summary)).toBe("제주시 2곳 · 서귀포시 1곳 · 최대 29km");
  });

  it("mentions the spread only when the spots are genuinely far apart", () => {
    const summary = spatialSummary(
      placed([
        spot({ contentId: "a", regionLabel: "제주 제주시", lat: 33.5, lng: 126.5 }),
        spot({ contentId: "b", regionLabel: "제주 서귀포시", lat: 33.51, lng: 126.51 }),
      ]),
    );

    expect(summary).toEqual({ places: "제주시 1곳 · 서귀포시 1곳", spread: null });
    expect(summaryLine(summary)).toBe("제주시 1곳 · 서귀포시 1곳");
  });

  it("falls back to a count when the spots scatter across many areas", () => {
    const summary = spatialSummary(
      placed([
        spot({ contentId: "a", regionLabel: "강원 강릉시", lat: 37.75, lng: 128.87 }),
        spot({ contentId: "b", regionLabel: "부산 해운대구", lat: 35.16, lng: 129.16 }),
        spot({ contentId: "c", regionLabel: "제주 제주시", lat: 33.5, lng: 126.5 }),
      ]),
    );

    expect(summary?.places).toBe("강릉시 1곳 · 해운대구 1곳 · +1");
    expect(summary?.spread).toMatch(/^최대 \d+km$/);
  });
});

describe("regionGroups with same-named districts", () => {
  it("keeps 서울 중구 and 대구 중구 apart", () => {
    const groups = regionGroups(
      placed([
        spot({ contentId: "a", regionLabel: "서울 중구", lat: 37.56, lng: 126.99 }),
        spot({ contentId: "b", regionLabel: "대구 중구", lat: 35.87, lng: 128.6 }),
      ]),
    );

    expect(groups.map((g) => g.label).sort()).toEqual(["대구 중구", "서울 중구"]);
  });

  it("still shortens a district whose name is unambiguous here", () => {
    const groups = regionGroups(
      placed([
        spot({ contentId: "a", regionLabel: "제주 제주시", lat: 33.5, lng: 126.5 }),
        spot({ contentId: "b", regionLabel: "제주 서귀포시", lat: 33.25, lng: 126.56 }),
      ]),
    );

    expect(groups.map((g) => g.label).sort()).toEqual(["서귀포시", "제주시"]);
  });

  it("never claims that two far-apart 중구 are the same place", () => {
    const summary = spatialSummary(
      placed([
        spot({ contentId: "a", regionLabel: "서울 중구", lat: 37.56, lng: 126.99 }),
        spot({ contentId: "b", regionLabel: "대구 중구", lat: 35.87, lng: 128.6 }),
      ]),
    );

    expect(summary).not.toContain("모두");
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
