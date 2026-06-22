import { removeById, containsId } from "@/features/saved/lib/optimistic";
import type { SpotCard } from "@/lib/api-types";

const card = (contentId: string): SpotCard => ({
  contentId,
  title: contentId,
  firstImageUrl: null,
  category: null,
});

describe("saved optimistic helpers", () => {
  const list = [card("a"), card("b"), card("c")];

  it("removeById drops the matching card and keeps order", () => {
    expect(removeById(list, "b").map((c) => c.contentId)).toEqual(["a", "c"]);
  });

  it("removeById is a no-op when absent", () => {
    expect(removeById(list, "z").map((c) => c.contentId)).toEqual(["a", "b", "c"]);
  });

  it("containsId is true only for present ids and false for undefined list", () => {
    expect(containsId(list, "a")).toBe(true);
    expect(containsId(list, "z")).toBe(false);
    expect(containsId(undefined, "a")).toBe(false);
  });
});
