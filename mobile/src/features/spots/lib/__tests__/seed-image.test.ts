import { preferredSeedImageUrl } from "@/features/spots/lib/seed-image";

const TARGET = "tong.visitkorea.or.kr/cms/resource/9/9_image1_1.jpg";
const tile = `https://img.pictrip.org/t1/320/aaa/${TARGET}`;
const hero = `https://img.pictrip.org/t1/1620/bbb/${TARGET}`;

describe("preferredSeedImageUrl", () => {
  it("upgrades a tile seed to the wider server url for the same upstream image", () => {
    expect(preferredSeedImageUrl(tile, hero)).toBe(hero);
  });

  it("keeps the seed when it is already the wider variant", () => {
    expect(preferredSeedImageUrl(hero, tile)).toBe(hero);
  });

  it("drops a transformed seed when the server declines to transform", () => {
    const raw = "https://tong.visitkorea.or.kr/cms/resource/9/9_image2_1.jpg";
    expect(preferredSeedImageUrl(tile, raw)).toBe(raw);
    expect(preferredSeedImageUrl(hero, raw)).toBe(raw);
  });

  it("keeps the seed when the upstream image differs", () => {
    const other = "https://img.pictrip.org/t1/1620/ccc/tong.visitkorea.or.kr/cms/other.jpg";
    expect(preferredSeedImageUrl(tile, other)).toBe(tile);
  });

  it("keeps the seed for non-proxy urls", () => {
    const raw = "https://tong.visitkorea.or.kr/cms/a_image1_1.jpg";
    expect(preferredSeedImageUrl(raw, "https://tong.visitkorea.or.kr/cms/a_image2_1.jpg")).toBe(
      raw,
    );
    expect(preferredSeedImageUrl(raw, hero)).toBe(raw);
    expect(preferredSeedImageUrl(tile, null)).toBe(tile);
  });

  it("keeps the seed when a proxy url is malformed", () => {
    expect(preferredSeedImageUrl(tile, "https://img.pictrip.org/t1/")).toBe(tile);
    expect(preferredSeedImageUrl(tile, `https://img.pictrip.org/t1/abc/bbb/${TARGET}`)).toBe(tile);
  });
});
