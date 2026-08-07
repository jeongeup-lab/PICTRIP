import {
  distanceLabel,
  distanceMeters,
  regionCount,
  regionOf,
  sortSaved,
  subline,
} from "@/features/saved/lib/sort";
import type { SpotCard } from "@/lib/api-types";

const spot = (over: Partial<SpotCard> & { contentId: string }): SpotCard => ({
  title: `spot-${over.contentId}`,
  firstImageUrl: null,
  addr1: null,
  mapx: null,
  mapy: null,
  category: null,
  ...over,
});

const SEOUL = { lat: 37.5665, lng: 126.978 };

describe("regionOf / subline", () => {
  it("takes the first address token as region", () => {
    expect(regionOf(spot({ contentId: "1", addr1: "경남 통영시 산양읍" }))).toBe("경남");
  });

  it("returns null for a blank address", () => {
    expect(regionOf(spot({ contentId: "1", addr1: "   " }))).toBeNull();
    expect(regionOf(spot({ contentId: "2" }))).toBeNull();
  });

  it("joins region and category", () => {
    expect(subline(spot({ contentId: "1", addr1: "경남 통영시", category: "자연관광지" }))).toBe(
      "경남 · 자연관광지",
    );
    expect(subline(spot({ contentId: "2", category: "쇼핑" }))).toBe("쇼핑");
  });
});

describe("distanceMeters / distanceLabel", () => {
  it("is null without coordinates or without a fix", () => {
    expect(distanceMeters(spot({ contentId: "1" }), SEOUL)).toBeNull();
    expect(distanceMeters(spot({ contentId: "2", mapx: 127, mapy: 37 }), null)).toBeNull();
  });

  it("measures from the user position", () => {
    const near = distanceMeters(spot({ contentId: "1", mapx: 126.99, mapy: 37.57 }), SEOUL);
    expect(near).not.toBeNull();
    expect(near!).toBeLessThan(2000);
  });

  it("formats by magnitude", () => {
    expect(distanceLabel(null)).toBe("—");
    expect(distanceLabel(324)).toBe("320m");
    expect(distanceLabel(4_120)).toBe("4.1km");
    expect(distanceLabel(41_400)).toBe("41km");
  });
});

describe("sortSaved", () => {
  const list = [
    spot({ contentId: "far", addr1: "전남 여수시", mapx: 127.7, mapy: 34.7 }),
    spot({ contentId: "none", addr1: "제주 제주시" }),
    spot({ contentId: "near", addr1: "서울 중구", mapx: 126.99, mapy: 37.56 }),
    spot({ contentId: "mid", addr1: "전남 순천시", mapx: 127.5, mapy: 35.0 }),
  ];

  it("keeps server order for recent", () => {
    expect(sortSaved(list, "recent", SEOUL).map((s) => s.contentId)).toEqual([
      "far",
      "none",
      "near",
      "mid",
    ]);
  });

  it("does not mutate the input", () => {
    sortSaved(list, "near", SEOUL);
    expect(list.map((s) => s.contentId)).toEqual(["far", "none", "near", "mid"]);
  });

  it("orders by distance and pushes unmeasurable spots last", () => {
    expect(sortSaved(list, "near", SEOUL).map((s) => s.contentId)).toEqual([
      "near",
      "mid",
      "far",
      "none",
    ]);
  });

  it("falls back to server order when there is no fix", () => {
    expect(sortSaved(list, "near", null).map((s) => s.contentId)).toEqual([
      "far",
      "none",
      "near",
      "mid",
    ]);
  });

  it("groups by region in first-seen order", () => {
    expect(sortSaved(list, "region", SEOUL).map((s) => s.contentId)).toEqual([
      "far",
      "mid",
      "none",
      "near",
    ]);
  });
});

describe("regionCount", () => {
  it("counts distinct regions and ignores missing addresses", () => {
    expect(
      regionCount([
        spot({ contentId: "1", addr1: "경남 통영시" }),
        spot({ contentId: "2", addr1: "경남 고성군" }),
        spot({ contentId: "3", addr1: "전남 여수시" }),
        spot({ contentId: "4" }),
      ]),
    ).toBe(2);
  });
});
