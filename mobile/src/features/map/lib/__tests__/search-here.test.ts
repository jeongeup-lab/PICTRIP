import { shouldShowSearchHere } from "@/features/map/lib/search-here";

describe("shouldShowSearchHere", () => {
  const base = { lat: 37.5, lng: 127 };
  it("is false when either point is null", () => {
    expect(shouldShowSearchHere(null, base, 3000)).toBe(false);
    expect(shouldShowSearchHere(base, null, 3000)).toBe(false);
  });
  it("is false for a small drift (< 30% of radius)", () => {
    // ~111m north — well under 900m threshold
    expect(shouldShowSearchHere({ lat: 37.501, lng: 127 }, base, 3000)).toBe(false);
  });
  it("is true once drift exceeds 30% of radius", () => {
    // ~1.1km north — over the 900m threshold
    expect(shouldShowSearchHere({ lat: 37.51, lng: 127 }, base, 3000)).toBe(true);
  });
});
