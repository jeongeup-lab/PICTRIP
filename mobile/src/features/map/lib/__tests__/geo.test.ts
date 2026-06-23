import { haversineMeters } from "@/features/map/lib/geo";

describe("haversineMeters", () => {
  it("is zero for identical points", () => {
    expect(haversineMeters({ lat: 37.5, lng: 127 }, { lat: 37.5, lng: 127 })).toBe(0);
  });
  it("approximates a known short distance (~1.11km per 0.01° lat)", () => {
    const d = haversineMeters({ lat: 37.5, lng: 127 }, { lat: 37.51, lng: 127 });
    expect(d).toBeGreaterThan(1100);
    expect(d).toBeLessThan(1120);
  });
});
