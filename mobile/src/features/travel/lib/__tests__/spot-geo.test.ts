import {
  placed,
  previewPoints,
  regionGroups,
  spatialSummary,
  spreadKm,
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

describe("previewPoints", () => {
  const box = { width: 100, height: 100, padding: 10 };

  it("keeps every point inside the padded box", () => {
    const points = previewPoints(
      placed([
        spot({ contentId: "a", lat: 33.2, lng: 126.2 }),
        spot({ contentId: "b", lat: 33.6, lng: 126.9 }),
        spot({ contentId: "c", lat: 33.4, lng: 126.5 }),
      ]),
      box,
    );

    points.forEach((p) => {
      expect(p.x).toBeGreaterThanOrEqual(10);
      expect(p.x).toBeLessThanOrEqual(90);
      expect(p.y).toBeGreaterThanOrEqual(10);
      expect(p.y).toBeLessThanOrEqual(90);
    });
  });

  it("puts the northern spot above the southern one", () => {
    const [north, south] = previewPoints(
      placed([
        spot({ contentId: "n", lat: 33.9, lng: 126.5 }),
        spot({ contentId: "s", lat: 33.1, lng: 126.5 }),
      ]),
      box,
    );

    expect(north.y).toBeLessThan(south.y);
  });

  it("centers a single spot instead of dividing by a zero span", () => {
    const [only] = previewPoints(placed([spot()]), box);

    expect(only.x).toBeCloseTo(50);
    expect(only.y).toBeCloseTo(50);
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

    expect(summary).toBe("모두 제주시에 있어요.");
  });

  it("names two areas with their counts", () => {
    const summary = spatialSummary(
      placed([
        spot({ contentId: "a", regionLabel: "제주 제주시", lat: 33.5, lng: 126.5 }),
        spot({ contentId: "b", regionLabel: "제주 제주시", lat: 33.51, lng: 126.52 }),
        spot({ contentId: "c", regionLabel: "제주 서귀포시", lat: 33.25, lng: 126.56 }),
      ]),
    );

    expect(summary).toBe("제주시 2곳 · 서귀포시 1곳이에요. 가장 먼 두 곳은 29km 떨어져요.");
  });

  it("mentions the spread only when the spots are genuinely far apart", () => {
    const summary = spatialSummary(
      placed([
        spot({ contentId: "a", regionLabel: "제주 제주시", lat: 33.5, lng: 126.5 }),
        spot({ contentId: "b", regionLabel: "제주 서귀포시", lat: 33.51, lng: 126.51 }),
      ]),
    );

    expect(summary).toBe("제주시 1곳 · 서귀포시 1곳이에요.");
  });

  it("falls back to a count when the spots scatter across many areas", () => {
    const summary = spatialSummary(
      placed([
        spot({ contentId: "a", regionLabel: "강원 강릉시", lat: 37.75, lng: 128.87 }),
        spot({ contentId: "b", regionLabel: "부산 해운대구", lat: 35.16, lng: 129.16 }),
        spot({ contentId: "c", regionLabel: "제주 제주시", lat: 33.5, lng: 126.5 }),
      ]),
    );

    expect(summary).toContain("등 3곳으로 나뉘어요.");
    expect(summary).toContain("km 떨어져요.");
  });
});
