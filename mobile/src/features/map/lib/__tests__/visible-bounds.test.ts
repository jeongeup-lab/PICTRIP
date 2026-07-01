import { clipBoundsToVisible } from "../visible-bounds";

const bounds = { sw: { lat: 37.0, lng: 126.0 }, ne: { lat: 38.0, lng: 127.0 } };

describe("clipBoundsToVisible", () => {
  it("keeps lng edges and the north edge unchanged", () => {
    const out = clipBoundsToVisible(bounds, 422, 844);
    expect(out.sw.lng).toBe(126.0);
    expect(out.ne).toEqual({ lat: 38.0, lng: 127.0 });
  });

  it("raises the south edge to the panel top (half snap = top 50%)", () => {
    const out = clipBoundsToVisible(bounds, 422, 844);
    // visibleSouthLat = 38 - (38-37) * (422/844) = 37.5
    expect(out.sw.lat).toBeCloseTo(37.5, 5);
  });

  it("clips more as the panel rises (smaller panelTopY → smaller band)", () => {
    const high = clipBoundsToVisible(bounds, 700, 844).sw.lat;
    const low = clipBoundsToVisible(bounds, 300, 844).sw.lat;
    expect(low).toBeGreaterThan(high); // panel higher → south edge nearer the top
  });

  it("returns the full bounds when the panel is at the bottom (fraction >= 1)", () => {
    expect(clipBoundsToVisible(bounds, 844, 844).sw.lat).toBeCloseTo(37.0, 5);
    expect(clipBoundsToVisible(bounds, 1000, 844).sw.lat).toBeCloseTo(37.0, 5);
  });

  it("never collapses below the 15% minimum visible band", () => {
    const out = clipBoundsToVisible(bounds, 10, 844); // fraction ~0.012 → clamped to 0.15
    expect(out.sw.lat).toBeCloseTo(37.85, 5);
    expect(out.sw.lat).toBeLessThan(out.ne.lat); // never inverted
  });

  it("falls back to the input bounds for a non-positive screen height", () => {
    expect(clipBoundsToVisible(bounds, 400, 0)).toEqual(bounds);
  });
});
