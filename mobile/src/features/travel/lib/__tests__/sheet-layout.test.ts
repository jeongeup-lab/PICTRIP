import { sheetHeightPx, sheetBottomPx, SHEET_ANIM_MS } from "@/features/travel/lib/sheet-layout";

const frame = { frameH: 844, insetTop: 59, insetBottom: 34 };

describe("sheet-layout", () => {
  it("collapsed는 독 높이만큼", () => {
    expect(sheetHeightPx({ ...frame, snap: "collapsed", keyboardPx: 0, dockPx: 72 })).toBe(72);
  });
  it("mid는 프레임의 58%", () => {
    expect(sheetHeightPx({ ...frame, snap: "mid", keyboardPx: 0, dockPx: 72 })).toBe(
      Math.round(844 * 0.58),
    );
  });
  it("full은 프레임의 88%", () => {
    expect(sheetHeightPx({ ...frame, snap: "full", keyboardPx: 0, dockPx: 72 })).toBe(
      Math.round(844 * 0.88),
    );
  });
  it("키보드가 있으면 남는 높이로 클램프", () => {
    expect(sheetHeightPx({ ...frame, snap: "full", keyboardPx: 336, dockPx: 72 })).toBe(
      844 - 336 - 59,
    );
  });
  it("시트 bottom은 키보드 높이 (없으면 0)", () => {
    expect(sheetBottomPx({ keyboardPx: 0 })).toBe(0);
    expect(sheetBottomPx({ keyboardPx: 336 })).toBe(336);
  });
  it("애니메이션 길이 상수", () => {
    expect(SHEET_ANIM_MS).toBe(280);
  });
});
