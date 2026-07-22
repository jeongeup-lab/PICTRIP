import type { Plan } from "@/features/plan/api";
import {
  mergeRecent,
  parseRecentPlans,
  recentSubtitle,
  toRecentPlan,
  type RecentPlan,
} from "@/features/plan/lib/recent-plans";

const entry = (id: string): RecentPlan => ({ id, title: id, days: 1, count: 3, thumb: null });

const plan: Plan = {
  planId: "Xq2",
  sourceTitle: "통영 당일 코스",
  sourceUrl: null,
  days: [
    {
      day: 1,
      regionLabel: "통영",
      slots: [
        {
          timeOfDay: "morning",
          travelMinutesFromPrev: null,
          place: {
            extracted: {
              name: "동피랑",
              nameKo: null,
              placeType: "attraction",
              regionHint: null,
              tip: null,
              orderHint: null,
            },
            spot: {
              source: "kto",
              contentId: "1",
              title: "동피랑",
              category: null,
              address: null,
              lat: null,
              lng: null,
              imageUrl: "a.jpg",
            },
            confidence: 1,
            status: "matched",
          },
        },
      ],
    },
  ],
  unplaced: [],
};

describe("toRecentPlan", () => {
  it("captures the id, title, day count and thumbnail", () => {
    expect(toRecentPlan(plan)).toEqual({
      id: "Xq2",
      title: "통영 당일 코스",
      days: 1,
      count: 1,
      thumb: "a.jpg",
    });
  });

  it("refuses a plan the backend never persisted", () => {
    expect(toRecentPlan({ ...plan, planId: null })).toBeNull();
  });
});

describe("mergeRecent", () => {
  it("moves a re-saved plan back to the front without duplicating it", () => {
    const merged = mergeRecent([entry("a"), entry("b")], entry("b"));
    expect(merged.map((p) => p.id)).toEqual(["b", "a"]);
  });

  it("caps the list at twenty entries", () => {
    const list = Array.from({ length: 20 }, (_, i) => entry(`p${i}`));
    expect(mergeRecent(list, entry("new"))).toHaveLength(20);
  });
});

describe("recentSubtitle", () => {
  it("describes a same-day plan by its visit count", () => {
    expect(recentSubtitle(entry("a"))).toBe("3곳 방문");
  });

  it("leads with the duration for multi-day plans", () => {
    expect(recentSubtitle({ ...entry("a"), days: 3 })).toBe("2박 3일 · 3곳 방문");
  });
});

describe("parseRecentPlans", () => {
  it("drops malformed entries rather than crashing the plan tab", () => {
    expect(parseRecentPlans('[{"id":"a","title":"t","days":1,"count":2},{"nope":1}]')).toHaveLength(
      1,
    );
  });

  it("returns an empty list for non-array json", () => {
    expect(parseRecentPlans('{"id":"a"}')).toEqual([]);
  });
});
