import {
  dockBasePx,
  mapFitPadding,
  panelBasePx,
  PANEL_CHIP_GAP_PX,
  PANEL_CHIP_ROW_PX,
} from "@/features/travel/lib/screen-layout";

describe("dockBasePx", () => {
  it("첫 화면 독은 입력 줄과 칩 줄만 쌓는다", () => {
    expect(dockBasePx({ primer: false, attached: false, chips: true })).toBe(46 + 12 + 42);
  });

  it("결과 패널이 칩을 가져가면 독은 입력 줄만 남는다", () => {
    expect(dockBasePx({ primer: false, attached: false, chips: false })).toBe(46 + 12);
  });

  it("위치 프라이머가 뜨면 그만큼 독이 위로 자란다", () => {
    expect(dockBasePx({ primer: true, attached: false, chips: true })).toBe(46 + 12 + 42 + 47);
  });

  it("첨부 배너는 칩 줄을 대신하면서 더 두껍다", () => {
    expect(dockBasePx({ primer: false, attached: true, chips: true })).toBe(46 + 12 + 73);
  });

  it("첨부 중에는 프라이머가 뜨지 않으므로 더하지 않는다", () => {
    expect(dockBasePx({ primer: true, attached: true, chips: true })).toBe(
      dockBasePx({ primer: false, attached: true, chips: true }),
    );
  });
});

describe("panelBasePx", () => {
  it("캐러셀을 뺀 패널은 답변 블록과 안쪽 여백만 센다", () => {
    expect(panelBasePx({ chips: false, carousel: true })).toBe(26 + 22 + 48);
  });

  it("칩 줄이 있으면 그만큼 더한다", () => {
    expect(panelBasePx({ chips: true, carousel: true })).toBe(
      panelBasePx({ chips: false, carousel: true }) + PANEL_CHIP_ROW_PX,
    );
  });

  it("카드가 없는 답에서는 칩 앞 여백을 캐러셀 대신 넣는다", () => {
    expect(panelBasePx({ chips: true, carousel: false })).toBe(
      panelBasePx({ chips: true, carousel: true }) + PANEL_CHIP_GAP_PX,
    );
  });
});

describe("mapFitPadding", () => {
  it("독과 패널이 덮는 만큼 아래를 비운다", () => {
    const pad = mapFitPadding({ safeTop: 59, dockHeight: 220 });

    expect(pad.bottom).toBe(220 + 24);
    expect(pad.top).toBe(59 + 96);
    expect(pad.left).toBe(40);
    expect(pad.right).toBe(40);
  });
});
