import { formatHeaderLabel } from "@/features/map/lib/region-label";
import type { RegionLabel } from "@/lib/api-types";

const seoul: RegionLabel = { sido: "서울", sigungu: "중구", dong: "명동", label: "서울 중구 명동" };

describe("formatHeaderLabel", () => {
  it("prefixes 현위치 with the dong when GPS-anchored", () => {
    expect(formatHeaderLabel("gps", seoul)).toBe("현위치 · 명동");
  });
  it("falls back to label when GPS-anchored without a dong", () => {
    expect(formatHeaderLabel("gps", { ...seoul, dong: null })).toBe("현위치 · 서울 중구 명동");
  });
  it("shows the plain label (no prefix) for region/pan anchors", () => {
    expect(formatHeaderLabel("region", seoul)).toBe("서울 중구 명동");
    expect(formatHeaderLabel("pan", seoul)).toBe("서울 중구 명동");
  });
  it("shows a placeholder when label is null", () => {
    expect(formatHeaderLabel("gps", null)).toBe("위치 확인 중");
  });
});
