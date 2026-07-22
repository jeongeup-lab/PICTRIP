import type { Plan, ResolvedPlace, ScheduleDay } from "@/features/plan/api";
import {
  collageImages,
  durationLabel,
  placeName,
  planThumb,
  planTitle,
  shortDurationLabel,
  shortRegion,
  totalSlots,
  totalTravelMinutes,
  unplacedSummary,
} from "@/features/plan/lib/plan-format";

const place = (title: string | null, imageUrl: string | null = null): ResolvedPlace => ({
  extracted: {
    name: title ?? "이름없음",
    nameKo: null,
    placeType: "attraction",
    regionHint: null,
    tip: null,
    orderHint: null,
  },
  spot: title
    ? {
        source: "kto",
        contentId: title,
        title,
        category: null,
        address: "경상남도 통영시 도남동",
        lat: 34.8,
        lng: 128.4,
        imageUrl,
      }
    : null,
  confidence: 1,
  status: title ? "matched" : "unmatched",
});

const day = (n: number, places: ResolvedPlace[], travel = 0): ScheduleDay => ({
  day: n,
  regionLabel: "통영",
  slots: places.map((p, i) => ({
    timeOfDay: "morning",
    place: p,
    travelMinutesFromPrev: i === 0 ? null : travel,
  })),
});

const plan = (over: Partial<Plan> = {}): Plan => ({
  planId: "abc123",
  sourceTitle: null,
  sourceUrl: null,
  days: [day(1, [place("동피랑", "a.jpg"), place("케이블카", "b.jpg")], 12)],
  unplaced: [],
  ...over,
});

describe("durationLabel", () => {
  it("labels a single day as a same-day course", () => {
    expect(durationLabel(1)).toBe("당일 코스");
    expect(shortDurationLabel(1)).toBe("당일");
  });

  it("labels multi-day plans as n-1박 n일", () => {
    expect(durationLabel(3)).toBe("2박 3일");
    expect(shortDurationLabel(2)).toBe("1박 2일");
  });
});

describe("shortRegion", () => {
  it("keeps only the first two address tokens", () => {
    expect(shortRegion("경상남도 통영시 도남동 634-1")).toBe("경상남도 통영시");
  });

  it("is empty for a missing address", () => {
    expect(shortRegion(null)).toBe("");
  });
});

describe("planTitle", () => {
  it("prefers the server-side source title", () => {
    expect(planTitle(plan({ sourceTitle: "통영 당일 코스" }))).toBe("통영 당일 코스");
  });

  it("falls back to the first day's region", () => {
    expect(planTitle(plan())).toBe("통영 여행");
  });

  it("falls back again when there is no region", () => {
    const days = [{ ...day(1, [place("동피랑")]), regionLabel: null }];
    expect(planTitle(plan({ days }))).toBe("이름 없는 일정");
  });
});

describe("plan totals", () => {
  it("counts every slot across days", () => {
    const p = plan({ days: [day(1, [place("a")]), day(2, [place("b"), place("c")])] });
    expect(totalSlots(p)).toBe(3);
  });

  it("sums travel minutes and ignores the first slot of each day", () => {
    expect(totalTravelMinutes(plan())).toBe(12);
  });
});

describe("plan images", () => {
  it("uses the first slot image as the thumbnail", () => {
    expect(planThumb(plan())).toBe("a.jpg");
  });

  it("is null when no slot has an image", () => {
    expect(planThumb(plan({ days: [day(1, [place("a")])] }))).toBeNull();
  });

  it("shows a single image rather than a two-image collage", () => {
    expect(collageImages(plan())).toEqual(["a.jpg"]);
  });

  it("shows three images once three are available", () => {
    const days = [day(1, [place("a", "a.jpg"), place("b", "b.jpg"), place("c", "c.jpg")])];
    expect(collageImages(plan({ days }))).toEqual(["a.jpg", "b.jpg", "c.jpg"]);
  });

  it("de-duplicates repeated image urls", () => {
    const days = [day(1, [place("a", "a.jpg"), place("b", "a.jpg")])];
    expect(collageImages(plan({ days }))).toEqual(["a.jpg"]);
  });
});

describe("placeName", () => {
  it("prefers the matched spot title", () => {
    expect(placeName(place("동피랑"))).toBe("동피랑");
  });

  it("falls back to the extracted name when unmatched", () => {
    expect(placeName(place(null))).toBe("이름없음");
  });
});

describe("unplacedSummary", () => {
  it("lists up to five names", () => {
    const names = ["a", "b", "c", "d", "e"].map((n) => place(n));
    expect(unplacedSummary(names)).toBe("a, b, c, d, e");
  });

  it("marks the overflow beyond five", () => {
    const names = ["a", "b", "c", "d", "e", "f"].map((n) => place(n));
    expect(unplacedSummary(names)).toBe("a, b, c, d, e 외");
  });
});
