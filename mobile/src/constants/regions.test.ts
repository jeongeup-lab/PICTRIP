import { REGIONS } from "./regions";

describe("REGIONS static tree", () => {
  it("has exactly 17 provinces", () => {
    expect(REGIONS).toHaveLength(17);
  });

  it("covers all 17 시·도 by full name", () => {
    const names = REGIONS.map((r) => r.fullName).sort();
    expect(names).toEqual(
      [
        "강원특별자치도",
        "경기도",
        "경상남도",
        "경상북도",
        "광주광역시",
        "대구광역시",
        "대전광역시",
        "부산광역시",
        "서울특별시",
        "세종특별자치시",
        "울산광역시",
        "인천광역시",
        "전라남도",
        "전북특별자치도",
        "제주특별자치도",
        "충청남도",
        "충청북도",
      ].sort(),
    );
  });

  it("every province except 세종 has at least one district", () => {
    for (const r of REGIONS) {
      if (r.fullName === "세종특별자치시") {
        expect(r.sigungus).toHaveLength(0);
      } else {
        expect(r.sigungus.length).toBeGreaterThan(0);
      }
    }
  });

  it("서울 has 25 자치구", () => {
    const seoul = REGIONS.find((r) => r.regionName === "서울");
    expect(seoul?.sigungus).toHaveLength(25);
  });

  it("matches expected district counts per province", () => {
    const expected: Record<string, number> = {
      서울: 25,
      부산: 16,
      대구: 9,
      인천: 10,
      광주: 5,
      대전: 5,
      울산: 5,
      세종: 0,
      경기: 31,
      강원: 18,
      충북: 11,
      충남: 15,
      전북: 14,
      전남: 22,
      경북: 22,
      경남: 18,
      제주: 2,
    };
    for (const r of REGIONS) {
      expect(r.sigungus).toHaveLength(expected[r.regionName]);
    }
  });

  it("has no empty district or region names", () => {
    for (const r of REGIONS) {
      expect(r.regionName.trim().length).toBeGreaterThan(0);
      expect(r.fullName.trim().length).toBeGreaterThan(0);
      for (const sg of r.sigungus) {
        expect(sg.sigunguName.trim().length).toBeGreaterThan(0);
      }
    }
  });

  it("has no duplicate district names within a province", () => {
    for (const r of REGIONS) {
      const names = r.sigungus.map((s) => s.sigunguName);
      expect(new Set(names).size).toBe(names.length);
    }
  });

  it("every centroid is within the Korean bounding box", () => {
    const inBox = (lat: number, lng: number) =>
      Number.isFinite(lat) &&
      Number.isFinite(lng) &&
      lat >= 33 &&
      lat <= 39 &&
      lng >= 124 &&
      lng <= 132;
    for (const r of REGIONS) {
      expect(inBox(r.centroid.lat, r.centroid.lng)).toBe(true);
      for (const sg of r.sigungus) {
        expect(inBox(sg.centroid.lat, sg.centroid.lng)).toBe(true);
      }
    }
  });
});
