import { RECENT_SPOTS_LIMIT, pushRecent } from "@/features/spots/lib/recent-spots";
import type { SpotCard } from "@/lib/api-types";

const spot = (contentId: string): SpotCard => ({
  contentId,
  title: `spot-${contentId}`,
  firstImageUrl: null,
  addr1: null,
  mapx: null,
  mapy: null,
  category: null,
});

describe("pushRecent", () => {
  it("puts the newest view first", () => {
    expect(pushRecent([spot("a")], spot("b")).map((s) => s.contentId)).toEqual(["b", "a"]);
  });

  it("moves a re-visited spot back to the front without duplicating", () => {
    const list = [spot("a"), spot("b"), spot("c")];
    expect(pushRecent(list, spot("c")).map((s) => s.contentId)).toEqual(["c", "a", "b"]);
  });

  it("caps the list", () => {
    const long = Array.from({ length: RECENT_SPOTS_LIMIT }, (_, i) => spot(`s${i}`));
    expect(pushRecent(long, spot("new"))).toHaveLength(RECENT_SPOTS_LIMIT);
    expect(pushRecent(long, spot("new"), 3).map((s) => s.contentId)).toEqual(["new", "s0", "s1"]);
  });

  it("does not mutate the input", () => {
    const list = [spot("a")];
    pushRecent(list, spot("b"));
    expect(list.map((s) => s.contentId)).toEqual(["a"]);
  });
});
