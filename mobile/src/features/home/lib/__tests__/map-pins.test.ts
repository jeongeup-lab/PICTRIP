import { bounds, center, countsOf, pinsFrom, placed } from "@/features/home/lib/map-pins";
import type { HomeSpotCard } from "@/features/home/api";

function card(over: Partial<HomeSpotCard> = {}): HomeSpotCard {
  return {
    contentId: "c1",
    title: "감천문화마을",
    regionLabel: "부산광역시 사하구",
    imageUrl: null,
    rank: null,
    dist: null,
    category: null,
    tag: null,
    anchorTitle: null,
    lat: 35.1,
    lng: 129.0,
    ...over,
  };
}

describe("placed", () => {
  it("drops cards the ETL never gave coordinates", () => {
    const kept = placed([card({ contentId: "a" }), card({ contentId: "b", lat: null })]);
    expect(kept.map((p) => p.card.contentId)).toEqual(["a"]);
  });
});

describe("pinsFrom", () => {
  it("swaps lat/lng into the map's x/y order", () => {
    const [pin] = pinsFrom(placed([card({ lat: 35.1, lng: 129.0 })]));
    expect(pin.mapx).toBe(129.0);
    expect(pin.mapy).toBe(35.1);
    expect(pin.contentId).toBe("c1");
  });
});

describe("center", () => {
  it("averages the placed cards", () => {
    const mid = center(placed([card({ lat: 35.0, lng: 129.0 }), card({ lat: 35.2, lng: 129.4 })]));
    expect(mid?.lat).toBeCloseTo(35.1, 6);
    expect(mid?.lng).toBeCloseTo(129.2, 6);
  });

  it("has nothing to centre on when no card is placed", () => {
    expect(center([])).toBeNull();
  });
});

describe("bounds", () => {
  it("widens a single pin so the map does not zoom to the street", () => {
    const box = bounds(placed([card({ lat: 35.1, lng: 129.0 })]));
    expect(box).not.toBeNull();
    expect(box!.ne.lat - box!.sw.lat).toBeCloseTo(0.02, 6);
    expect(box!.ne.lng - box!.sw.lng).toBeCloseTo(0.02, 6);
  });

  it("keeps a spread wider than the floor", () => {
    const box = bounds(placed([card({ lat: 35.0, lng: 129.0 }), card({ lat: 35.5, lng: 129.6 })]));
    expect(box!.ne.lat - box!.sw.lat).toBeCloseTo(0.5, 6);
  });
});

describe("countsOf", () => {
  it("splits the ranking into the three words the overlay says", () => {
    const counts = countsOf([
      card({ category: "카페" }),
      card({ category: "디저트" }),
      card({ category: "한식" }),
      card({ category: "자연관광지" }),
      card({ category: null }),
    ]);
    expect(counts).toEqual({ cafe: 2, food: 1, spot: 2 });
  });
});
