import {
  travelSheetSnapY,
  sheetHeightOverRoot,
  CHIPS_PX,
  DEFAULT_TAB_BAR_PX,
  TAB_BAR_CONTENT_PX,
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

describe("tab bar height", () => {
  it("reaches the standard tab bar once the home indicator inset is added", () => {
    const HOME_INDICATOR_PX = 34;
    expect(TAB_BAR_CONTENT_PX + HOME_INDICATOR_PX).toBe(DEFAULT_TAB_BAR_PX);
  });

  it("leaves only the bar itself on devices without a bottom inset", () => {
    expect(TAB_BAR_CONTENT_PX + 0).toBe(TAB_BAR_CONTENT_PX);
    expect(travelSheetSnapY(852, TAB_BAR_CONTENT_PX).peek).toBeGreaterThan(
      travelSheetSnapY(852, DEFAULT_TAB_BAR_PX).peek,
    );
  });
});

describe("sheetHeightOverRoot", () => {
  const SCREEN_H = 852;
  const TAB_BAR = 83;

  it("measures the sheet from the root view, which stops above the tab bar", () => {
    const snapY = travelSheetSnapY(SCREEN_H, TAB_BAR);
    const visibleOnScreen = SCREEN_H - snapY.peek;

    expect(sheetHeightOverRoot(SCREEN_H, TAB_BAR, snapY.peek)).toBe(visibleOnScreen - TAB_BAR);
  });

  it("never goes negative when the sheet sits below the root", () => {
    expect(sheetHeightOverRoot(SCREEN_H, TAB_BAR, SCREEN_H)).toBe(0);
  });
});
