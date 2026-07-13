import { toGridBlocks } from "@/features/explore/lib/grid-blocks";
import type { OverseasPost } from "@/features/feed/posts-api";

function posts(n: number): OverseasPost[] {
  return Array.from({ length: n }, (_, i) => ({
    id: i + 1,
    nameKo: `장소 ${i + 1}`,
    countryCode: "JP",
    countryNameKo: "일본",
    descriptionKo: null,
    imageUrl: `https://upload.wikimedia.org/${i + 1}.jpg`,
    imageAuthor: null,
    imageLicense: null,
    imageLicenseUrl: null,
    imageSourceUrl: `https://commons.wikimedia.org/${i + 1}`,
  }));
}

describe("toGridBlocks", () => {
  it("turns 9 items into row3, big, row3", () => {
    const { blocks, leftover } = toGridBlocks(posts(9));
    expect(blocks.map((b) => b.type)).toEqual(["row3", "big", "row3"]);
    expect(leftover).toEqual([]);
  });

  it("keeps a partial tail under 3 items in leftover, not in blocks", () => {
    const { blocks, leftover } = toGridBlocks(posts(10));
    expect(blocks.map((b) => b.type)).toEqual(["row3", "big", "row3"]);
    expect(leftover).toHaveLength(1);
    expect(leftover[0].id).toBe(10);
  });

  it("a big block consumes exactly 3 items (1 big + 2 side)", () => {
    const { blocks } = toGridBlocks(posts(9));
    const big = blocks.find((b) => b.type === "big");
    expect(big).toBeDefined();
    if (big && big.type === "big") {
      expect(big.side).toHaveLength(2);
      expect([big.big.id, ...big.side.map((s) => s.id)]).toEqual([4, 5, 6]);
    }
  });

  it("returns fewer-than-3 items entirely in leftover", () => {
    const { blocks, leftover } = toGridBlocks(posts(2));
    expect(blocks).toEqual([]);
    expect(leftover).toHaveLength(2);
  });

  it("continues the row3/big cycle across 18 items", () => {
    const { blocks } = toGridBlocks(posts(18));
    expect(blocks.map((b) => b.type)).toEqual(["row3", "big", "row3", "row3", "big", "row3"]);
  });
});
