import { withUserDistance } from "@/features/map/lib/user-distance";
import type { NearbySpot } from "@/lib/api-types";

const spot = (over: Partial<NearbySpot>): NearbySpot => ({
  contentId: "1",
  title: "t",
  firstImageUrl: null,
  category: null,
  categoryGroup: null,
  mapx: 126.9784,
  mapy: 37.5666,
  dist: 12345,
  regionName: null,
  sigunguName: null,
  overview: null,
  ...over,
});

describe("withUserDistance", () => {
  const gps = { lat: 37.5666, lng: 126.9784 };

  it("replaces the server dist with the distance from the user's GPS fix", () => {
    const [s] = withUserDistance([spot({ mapy: 37.5756, mapx: 126.9784 })], gps);
    expect(s.dist).toBeGreaterThan(900);
    expect(s.dist).toBeLessThan(1100);
  });

  it("is ~0 for a spot at the user's own position", () => {
    const [s] = withUserDistance([spot({})], gps);
    expect(s.dist).toBeLessThan(1);
  });

  it("nulls dist when there is no GPS fix (never shows a map-center distance)", () => {
    const [s] = withUserDistance([spot({})], null);
    expect(s.dist).toBeNull();
  });

  it("nulls dist when the spot has no coordinates", () => {
    const [s] = withUserDistance([spot({ mapx: null, mapy: null })], gps);
    expect(s.dist).toBeNull();
  });
});
