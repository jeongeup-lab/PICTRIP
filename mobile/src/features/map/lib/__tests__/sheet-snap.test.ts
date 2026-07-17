import { sheetSnapY, CARD_PX, HALF_VISIBLE_PX, PEEK_VISIBLE_PX } from "../sheet-snap";

describe("sheetSnapY", () => {
  it("half reveals exactly one card more than peek", () => {
    expect(HALF_VISIBLE_PX - PEEK_VISIBLE_PX).toBe(CARD_PX);
    for (const h of [667, 852, 932]) {
      const y = sheetSnapY(h);
      expect(y.peek - y.half).toBe(CARD_PX);
    }
  });

  it("half reveal budget is fixed px, not a screen ratio", () => {
    const short = sheetSnapY(667);
    const tall = sheetSnapY(932);
    expect(667 - short.half).toBe(HALF_VISIBLE_PX);
    expect(932 - tall.half).toBe(HALF_VISIBLE_PX);
  });

  it("keeps full < half < peek ordering on every device height", () => {
    for (const h of [568, 667, 852, 932]) {
      const y = sheetSnapY(h);
      expect(y.full).toBeLessThan(y.half);
      expect(y.half).toBeLessThan(y.peek);
    }
  });
});
