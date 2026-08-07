import { coordsOf, distanceReading, spotDistanceKm } from "../distance";
import type { TravelSpot } from "@/features/travel/api";

const spot = (over: Partial<TravelSpot> = {}): TravelSpot => ({
  contentId: "1",
  title: "무릉계곡",
  regionLabel: "강원도 동해시",
  imageUrl: null,
  tag: null,
  lat: 37.5,
  lng: 129.0,
  ...over,
});

describe("coordsOf", () => {
  it("좌표가 반쪽이면 위치로 치지 않는다", () => {
    expect(coordsOf(spot({ lat: null }))).toBeNull();
    expect(coordsOf(spot({ lng: null }))).toBeNull();
    expect(coordsOf(spot())).toEqual({ lat: 37.5, lng: 129.0 });
  });
});

describe("spotDistanceKm", () => {
  it("기준점이나 좌표가 없으면 재지 않는다", () => {
    expect(spotDistanceKm(spot(), null)).toBeNull();
    expect(spotDistanceKm(spot({ lat: null, lng: null }), { lat: 37.5, lng: 129.0 })).toBeNull();
  });

  it("위도 1도는 약 111km", () => {
    const km = spotDistanceKm(spot(), { lat: 36.5, lng: 129.0 });
    expect(km).not.toBeNull();
    expect(Math.round(km as number)).toBe(111);
  });
});

describe("distanceReading", () => {
  it("1km 미만은 미터로 읽는다", () => {
    expect(distanceReading(0.34)).toEqual({ value: "340", unit: "m" });
  });

  it("가까운 거리는 소수점 한 자리까지 남긴다", () => {
    expect(distanceReading(1.14)).toEqual({ value: "1.1", unit: "km" });
  });

  it("먼 거리는 정수 km 로 줄인다", () => {
    expect(distanceReading(12.4)).toEqual({ value: "12", unit: "km" });
  });
});
