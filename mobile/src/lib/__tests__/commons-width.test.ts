import { PixelRatio } from "react-native";
import { commonsWidthFor, COMMONS_WIDTHS } from "@/lib/commons-width";

describe("commonsWidthFor", () => {
  const mockRatio = (ratio: number) => jest.spyOn(PixelRatio, "get").mockReturnValue(ratio);

  afterEach(() => jest.restoreAllMocks());

  it("only ever returns Wikimedia standard thumbnail widths", () => {
    mockRatio(3);
    const standard = [20, 40, 60, 120, 250, 330, 500, 960, 1280, 1920, 3840];
    for (let dp = 10; dp <= 900; dp += 7) {
      expect(standard).toContain(commonsWidthFor(dp));
    }
  });

  it("rounds a grid tile up to the next standard width", () => {
    mockRatio(2);
    expect(commonsWidthFor(130)).toBe(330);
    expect(commonsWidthFor(180)).toBe(500);
  });

  it("scales with the device pixel ratio", () => {
    mockRatio(3);
    expect(commonsWidthFor(130)).toBe(500);
  });

  it("caps at the largest bucket for full-width heroes", () => {
    mockRatio(3);
    expect(commonsWidthFor(800)).toBe(COMMONS_WIDTHS[COMMONS_WIDTHS.length - 1]);
  });
});
