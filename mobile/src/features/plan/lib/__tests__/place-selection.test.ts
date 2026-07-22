import type { PlaceType, ResolvedPlace, ResolveStatus } from "@/features/plan/api";
import {
  defaultSelection,
  requestedDays,
  splitPlaces,
  toggleIndex,
} from "@/features/plan/lib/place-selection";

const place = (status: ResolveStatus, placeType: PlaceType = "attraction"): ResolvedPlace => ({
  extracted: {
    name: "n",
    nameKo: null,
    placeType,
    regionHint: null,
    tip: null,
    orderHint: null,
  },
  spot: null,
  confidence: 0,
  status,
});

describe("splitPlaces", () => {
  it("drops region rows entirely — they are not visitable places", () => {
    const { usable, missing } = splitPlaces([place("matched", "region"), place("matched")]);
    expect(usable).toEqual([1]);
    expect(missing).toEqual([]);
  });

  it("separates unmatched places into the missing bucket", () => {
    const { usable, missing } = splitPlaces([
      place("matched"),
      place("unmatched"),
      place("naver_only"),
      place("ambiguous"),
    ]);
    expect(usable).toEqual([0, 2, 3]);
    expect(missing).toEqual([1]);
  });
});

describe("defaultSelection", () => {
  it("pre-selects every usable place", () => {
    expect(defaultSelection([place("matched"), place("unmatched"), place("matched")])).toEqual([
      0, 2,
    ]);
  });
});

describe("toggleIndex", () => {
  it("adds a missing index and keeps the list sorted", () => {
    expect(toggleIndex([0, 2], 1)).toEqual([0, 1, 2]);
  });

  it("removes an index that is already selected", () => {
    expect(toggleIndex([0, 1, 2], 1)).toEqual([0, 2]);
  });
});

describe("requestedDays", () => {
  it("keeps a day count the backend accepts", () => {
    expect(requestedDays(3)).toBe(3);
  });

  it("drops out-of-range day counts so the backend infers instead", () => {
    expect(requestedDays(0)).toBeNull();
    expect(requestedDays(8)).toBeNull();
    expect(requestedDays(null)).toBeNull();
  });
});
