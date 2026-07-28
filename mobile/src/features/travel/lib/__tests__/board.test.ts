import { boardPinHeight, mergeBoardSpots, splitBoardColumns } from "@/features/travel/lib/board";
import type { TravelSpot } from "@/features/travel/api";

const spot = (contentId: string): TravelSpot => ({
  contentId,
  title: `spot-${contentId}`,
  regionLabel: "강원 삼척",
  imageUrl: null,
  tag: null,
  lat: null,
  lng: null,
});

describe("mergeBoardSpots", () => {
  it("interleaves lists round-robin so every channel surfaces near the top", () => {
    const merged = mergeBoardSpots([
      [spot("h1"), spot("h2")],
      [spot("d1"), spot("d2")],
      [spot("a1")],
    ]);
    expect(merged.map((s) => s.contentId)).toEqual(["h1", "d1", "a1", "h2", "d2"]);
  });

  it("drops duplicates by contentId keeping the first occurrence", () => {
    const merged = mergeBoardSpots([
      [spot("h1"), spot("x")],
      [spot("x"), spot("d2")],
    ]);
    expect(merged.map((s) => s.contentId)).toEqual(["h1", "x", "d2"]);
  });

  it("caps the merged board", () => {
    const many = Array.from({ length: 10 }, (_, i) => spot(`h${i}`));
    expect(mergeBoardSpots([many, many.map((s) => spot(`d${s.contentId}`))], 4)).toHaveLength(4);
  });

  it("returns empty for empty input", () => {
    expect(mergeBoardSpots([])).toEqual([]);
    expect(mergeBoardSpots([[], []])).toEqual([]);
  });
});

describe("boardPinHeight", () => {
  it("raises every third pin to stagger the two columns", () => {
    expect([0, 1, 2, 3, 4].map(boardPinHeight)).toEqual([178, 224, 178, 178, 224]);
  });
});

describe("splitBoardColumns", () => {
  it("deals cells alternately into two columns", () => {
    expect(splitBoardColumns(["a", "b", "c", "d", "e"])).toEqual([
      ["a", "c", "e"],
      ["b", "d"],
    ]);
  });

  it("keeps a lone cell in the left column", () => {
    expect(splitBoardColumns(["a"])).toEqual([["a"], []]);
  });
});
