import { regionCount, regionOf, subline } from "@/features/saved/lib/region";
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
