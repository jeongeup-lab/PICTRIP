import { detailSheetSnapY, BASE_MARGIN_PX, MIN_BASE_VISIBLE_PX } from "../detail-sheet-snap";

describe("detailSheetSnapY", () => {
  const H = 852;
  const tabBar = 83;

  it("base reveals exactly the measured above-fold hero over the tab bar", () => {
    const aboveFold = 470;
    const { base } = detailSheetSnapY(H, aboveFold, tabBar);
    expect(H - base - tabBar).toBe(aboveFold + BASE_MARGIN_PX);
  });

  it("keeps full < base on every device height", () => {
    for (const h of [667, 852, 932]) {
      const y = detailSheetSnapY(h, 470, tabBar);
      expect(y.full).toBeLessThan(y.base);
    }
  });

  it("uses a screen-ratio fallback before the hero is measured", () => {
    const { base, full } = detailSheetSnapY(H, null, tabBar);
    expect(full).toBeLessThan(base);
    expect(base).toBeLessThan(H); // partially open, not closed
  });

  it("never opens shorter than the minimum visible height", () => {
    const { base } = detailSheetSnapY(H, 10, tabBar); // degenerate measurement
    expect(H - base - tabBar).toBeGreaterThanOrEqual(MIN_BASE_VISIBLE_PX);
  });
});
