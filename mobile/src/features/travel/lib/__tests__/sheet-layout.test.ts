import {
  clampToSheet,
  nearestSnap,
  nextSnap,
  settleSnap,
  SHEET_ANIM_MS,
  SHEET_HEADER_PX,
  sheetBottomPx,
  sheetHeightPx,
  snapHeights,
} from "@/features/travel/lib/sheet-layout";

const frame = { frameH: 844, insetTop: 59, insetBottom: 34 };
const metrics = { ...frame, keyboardPx: 0, dockPx: 72 };

describe("sheet-layout", () => {
  it("collapsed는 독 높이 + 드래그 손잡이", () => {
    expect(sheetHeightPx({ ...metrics, snap: "collapsed" })).toBe(72 + SHEET_HEADER_PX);
  });
  it("mid는 프레임의 58%", () => {
    expect(sheetHeightPx({ ...metrics, snap: "mid" })).toBe(Math.round(844 * 0.58));
  });
  it("full은 프레임의 88%", () => {
    expect(sheetHeightPx({ ...metrics, snap: "full" })).toBe(Math.round(844 * 0.88));
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

describe("sheet drag", () => {
  const heights = snapHeights(metrics);

  it("스냅 높이는 collapsed < mid < full", () => {
    expect(heights.collapsed).toBeLessThan(heights.mid);
    expect(heights.mid).toBeLessThan(heights.full);
  });

  it("드래그 높이는 collapsed~full 사이로 잘린다", () => {
    expect(clampToSheet(-500, heights)).toBe(heights.collapsed);
    expect(clampToSheet(9999, heights)).toBe(heights.full);
    expect(clampToSheet(heights.mid, heights)).toBe(heights.mid);
  });

  it("천천히 놓으면 가장 가까운 스냅에 붙는다", () => {
    expect(nearestSnap(heights, heights.collapsed + 4)).toBe("collapsed");
    expect(nearestSnap(heights, heights.mid - 20)).toBe("mid");
    expect(nearestSnap(heights, heights.full - 10)).toBe("full");
  });

  it("위로 튕기면 한 단계 올라간다", () => {
    expect(
      settleSnap({ heights, from: "collapsed", height: heights.collapsed, velocityY: -1.5 }),
    ).toBe("mid");
    expect(settleSnap({ heights, from: "mid", height: heights.mid, velocityY: -1.5 })).toBe("full");
  });

  it("아래로 튕기면 한 단계 내려간다", () => {
    expect(settleSnap({ heights, from: "full", height: heights.full, velocityY: 1.5 })).toBe("mid");
    expect(settleSnap({ heights, from: "mid", height: heights.mid, velocityY: 1.5 })).toBe(
      "collapsed",
    );
  });

  it("끝에서 더 튕겨도 넘어가지 않는다", () => {
    expect(nextSnap("full", 1)).toBe("full");
    expect(nextSnap("collapsed", -1)).toBe("collapsed");
  });

  it("느리게 조금만 끌면 원래 스냅에 되돌아간다", () => {
    expect(settleSnap({ heights, from: "mid", height: heights.mid - 12, velocityY: -0.1 })).toBe(
      "mid",
    );
  });

  it("느려도 절반 넘게 끌었으면 다음 스냅으로 넘어간다", () => {
    const past = (heights.mid + heights.full) / 2 + 20;
    expect(settleSnap({ heights, from: "mid", height: past, velocityY: -0.1 })).toBe("full");
  });
});
