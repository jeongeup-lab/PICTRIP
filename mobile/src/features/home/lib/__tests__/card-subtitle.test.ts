import { anchorBadge, categorySubtitle, distanceSubtitle } from "@/features/home/lib/card-subtitle";
import type { HomeSpotCard } from "@/features/home/api";

const card = (over: Partial<HomeSpotCard> = {}): HomeSpotCard => ({
  contentId: "1",
  title: "감천문화마을",
  regionLabel: "부산광역시 사하구",
  imageUrl: null,
  rank: null,
  dist: null,
  category: null,
  tag: null,
  anchorTitle: null,
  ...over,
});

describe("distanceSubtitle", () => {
  it("shows the walking distance when coordinates were sent", () => {
    expect(distanceSubtitle(card({ dist: 4700 }))).toBe("여기서 4.7km");
  });

  it("falls back to the region when there is no distance", () => {
    expect(distanceSubtitle(card())).toBe("부산광역시 사하구");
  });
});

describe("categorySubtitle", () => {
  it("joins category and distance", () => {
    expect(categorySubtitle(card({ category: "중식당", dist: 724 }))).toBe("중식당 · 724m");
  });

  it("names the region instead of a distance once the spot is a trip away", () => {
    expect(categorySubtitle(card({ category: "사당", dist: 162_645 }))).toBe(
      "사당 · 부산광역시 사하구",
    );
  });

  it("names the region when there are no coordinates to measure from", () => {
    expect(categorySubtitle(card({ category: "카페" }))).toBe("카페 · 부산광역시 사하구");
  });

  it("falls back to the region alone when the spot has no category", () => {
    expect(categorySubtitle(card())).toBe("부산광역시 사하구");
  });
});

describe("anchorBadge", () => {
  it("names the saved spot the recommendation came from", () => {
    expect(anchorBadge(card({ anchorTitle: "광안리해수욕장" }))).toBe(
      "저장한 광안리해수욕장과 비슷한 곳",
    );
  });

  it("picks 와 when the anchor ends without a coda", () => {
    expect(anchorBadge(card({ anchorTitle: "해운대" }))).toBe("저장한 해운대와 비슷한 곳");
  });

  it("clips a long anchor so the trailing phrase survives", () => {
    const badge = anchorBadge(card({ anchorTitle: "국립중앙박물관 어린이박물관 별관" }));
    expect(badge).toContain("…");
    expect(badge?.endsWith("비슷한 곳")).toBe(true);
  });

  it("is absent when no anchor came back", () => {
    expect(anchorBadge(card())).toBeNull();
  });

  it("treats a blank anchor as no anchor", () => {
    expect(anchorBadge(card({ anchorTitle: "   " }))).toBeNull();
  });
});
