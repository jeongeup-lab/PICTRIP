import type { Plan, ScheduleDay } from "@/features/plan/api";
import { buildPlanRouteHtml, planRoutePoints } from "@/features/plan/lib/plan-route-html";

const slot = (lat: number | null, lng: number | null) => ({
  timeOfDay: "morning" as const,
  travelMinutesFromPrev: null,
  place: {
    extracted: {
      name: "n",
      nameKo: null,
      placeType: "attraction" as const,
      regionHint: null,
      tip: null,
      orderHint: null,
    },
    spot: {
      source: "kto" as const,
      contentId: "1",
      title: "n",
      category: null,
      address: null,
      lat,
      lng,
      imageUrl: null,
    },
    confidence: 1,
    status: "matched" as const,
  },
});

const day = (n: number, coords: [number | null, number | null][]): ScheduleDay => ({
  day: n,
  regionLabel: null,
  slots: coords.map(([lat, lng]) => slot(lat, lng)),
});

const plan: Plan = {
  planId: "p",
  sourceTitle: null,
  sourceUrl: null,
  days: [
    day(1, [
      [34.8, 128.4],
      [34.9, 128.5],
    ]),
    day(2, [[35.1, 129.0]]),
  ],
  unplaced: [],
};

describe("planRoutePoints", () => {
  it("walks every day in order when no day is focused", () => {
    expect(planRoutePoints(plan, null)).toEqual([
      { lat: 34.8, lng: 128.4 },
      { lat: 34.9, lng: 128.5 },
      { lat: 35.1, lng: 129.0 },
    ]);
  });

  it("limits the route to the focused day", () => {
    expect(planRoutePoints(plan, 2)).toEqual([{ lat: 35.1, lng: 129.0 }]);
  });

  it("skips slots with no coordinates", () => {
    const partial: Plan = {
      ...plan,
      days: [
        day(1, [
          [null, null],
          [34.8, 128.4],
        ]),
      ],
    };
    expect(planRoutePoints(partial, null)).toEqual([{ lat: 34.8, lng: 128.4 }]);
  });
});

describe("buildPlanRouteHtml", () => {
  it("embeds the js key as a json literal so quotes cannot break out", () => {
    expect(buildPlanRouteHtml('a"b')).toContain('var key = "a\\"b"');
  });

  it("reports a missing key instead of loading the sdk", () => {
    expect(buildPlanRouteHtml("")).toContain("missing-js-key");
  });
});
