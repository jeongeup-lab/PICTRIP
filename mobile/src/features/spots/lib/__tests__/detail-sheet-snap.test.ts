import {
  detailSheetSnapY,
  BASE_MARGIN_PX,
  MIN_BASE_VISIBLE_PX,
  MIN_PEEK_VISIBLE_PX,
  HERO_BELOW_FOLD_PX,
  HERO_PEEK_BELOW_FOLD_PX,
} from "../detail-sheet-snap";

describe("detailSheetSnapY", () => {
  const H = 852;
  const tabBar = 83;
  const heroH = 620;

  it("base reveals the hero up to just above the 전체 사진 button", () => {
    const { base } = detailSheetSnapY(H, heroH, tabBar, true);
    expect(H - base - tabBar).toBe(heroH - HERO_BELOW_FOLD_PX + BASE_MARGIN_PX);
  });

  it("peek folds the photo strip away → lower (larger y) than base", () => {
    const { peek, base } = detailSheetSnapY(H, heroH, tabBar, true);
    expect(H - peek - tabBar).toBe(heroH - HERO_PEEK_BELOW_FOLD_PX + BASE_MARGIN_PX);
    expect(peek).toBeGreaterThan(base);
  });

  it("keeps full < base < peek on every device height", () => {
    for (const h of [667, 852, 932]) {
      const y = detailSheetSnapY(h, heroH, tabBar, true);
      expect(y.full).toBeLessThan(y.base);
      expect(y.base).toBeLessThan(y.peek);
    }
  });

  it("collapses peek to base when there is no gallery", () => {
    const { peek, base } = detailSheetSnapY(H, heroH, tabBar, false);
    expect(peek).toBe(base);
  });

  it("uses a screen-ratio fallback before the hero is measured", () => {
    const { base, peek, full } = detailSheetSnapY(H, null, tabBar, true);
    expect(full).toBeLessThan(base);
    expect(base).toBeLessThan(H);
    expect(peek).toBe(base);
  });

  it("never opens base shorter than the minimum visible height", () => {
    const { base } = detailSheetSnapY(H, 100, tabBar, true);
    expect(H - base - tabBar).toBeGreaterThanOrEqual(MIN_BASE_VISIBLE_PX);
  });

  it("never opens peek shorter than the minimum visible height", () => {
    const { peek } = detailSheetSnapY(H, 100, tabBar, true);
    expect(H - peek - tabBar).toBeGreaterThanOrEqual(MIN_PEEK_VISIBLE_PX);
  });
});
