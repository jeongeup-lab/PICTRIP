import {
  travelSheetSnapY,
  CHIPS_PX,
  FIELD_PX,
  HANDLE_ZONE_PX,
  ROWS_PX,
  START_PX,
} from "../sheet-snap";
import { FULL_TOP_RATIO } from "@/lib/sheet-snap";

const SCREEN_H = 844;

describe("travelSheetSnapY", () => {
  it("peek 은 검색 필드·칩·시작 액션이 다 보이는 높이", () => {
    const snapY = travelSheetSnapY(SCREEN_H, 83);
    const visible = SCREEN_H - snapY.peek;

    expect(visible).toBe(HANDLE_ZONE_PX + FIELD_PX + CHIPS_PX + START_PX + 83);
  });

  it("half 은 결과 몇 줄만큼 더 올라온다", () => {
    const snapY = travelSheetSnapY(SCREEN_H, 83);

    expect(snapY.peek - snapY.half).toBe(ROWS_PX);
  });

  it("full 은 지도를 한 줄 남기고 덮는다", () => {
    const snapY = travelSheetSnapY(SCREEN_H, 83);

    expect(snapY.full).toBe(SCREEN_H * FULL_TOP_RATIO);
    expect(snapY.full).toBeLessThan(snapY.half);
  });

  it("탭바가 두꺼운 기기에선 peek 도 같이 올라온다", () => {
    expect(travelSheetSnapY(SCREEN_H, 100).peek).toBeLessThan(travelSheetSnapY(SCREEN_H, 83).peek);
  });
});
