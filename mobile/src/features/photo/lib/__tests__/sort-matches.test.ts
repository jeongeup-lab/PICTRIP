import { sortMatches } from "@/features/photo/lib/sort-matches";
import type { PhotoMatch } from "@/lib/api-types";

const m = (contentId: string, similarity: number, distance: number | null): PhotoMatch => ({
  contentId,
  title: contentId,
  firstImageUrl: null,
  category: null,
  similarity,
  distance,
});

describe("sortMatches", () => {
  const data = [m("a", 0.7, 5000), m("b", 0.9, 12000), m("c", 0.8, null)];

  it("similarity sorts by similarity desc", () => {
    expect(sortMatches(data, "similarity").map((x) => x.contentId)).toEqual(["b", "c", "a"]);
  });
  it("distance sorts asc with nulls last", () => {
    expect(sortMatches(data, "distance").map((x) => x.contentId)).toEqual(["a", "b", "c"]);
  });
  it("distance ties break by similarity desc", () => {
    const tie = [m("x", 0.6, 1000), m("y", 0.95, 1000)];
    expect(sortMatches(tie, "distance").map((x) => x.contentId)).toEqual(["y", "x"]);
  });
  it("does not mutate the input", () => {
    const input = [...data];
    sortMatches(input, "similarity");
    expect(input.map((x) => x.contentId)).toEqual(["a", "b", "c"]);
  });
});
