import { coordsOf, distanceLabel, distanceReading, spotDistanceKm } from "../distance";
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

describe("distanceLabel", () => {
  it("서버가 잰 거리가 있으면 그 문구를 그대로 쓴다", () => {
    expect(distanceLabel("420m", 450)).toBe("420m");
    expect(distanceLabel("2.4km", 450)).toBe("2.4km");
  });

  it("기기 위치를 모를 때도 서버 거리는 남는다", () => {
    expect(distanceLabel("420m", null)).toBe("420m");
  });

  it("서버가 거리를 주지 않으면 기기 위치로 잰 값을 읽는다", () => {
    expect(distanceLabel(null, 2.44)).toBe("2.4km");
    expect(distanceLabel("한산", 2.44)).toBe("2.4km");
  });

  it("양쪽 다 없으면 붙일 거리가 없다", () => {
    expect(distanceLabel(null, null)).toBeNull();
    expect(distanceLabel("한산", null)).toBeNull();
  });
});

describe("distanceReading at the origin", () => {
  it("shows the anchored place itself as 0m, not a floor of 10m", () => {
    expect(distanceReading(0)).toEqual({ value: "0", unit: "m" });
  });

  it("still floors a real but tiny distance so it is not rounded to nothing", () => {
    expect(distanceReading(0.002)).toEqual({ value: "10", unit: "m" });
  });
});
