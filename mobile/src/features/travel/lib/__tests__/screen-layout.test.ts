import { dockBasePx, mapFitPadding } from "@/features/travel/lib/screen-layout";

describe("dockBasePx", () => {
  it("기본 독은 입력 줄과 아래 패딩만 쌓는다", () => {
    expect(dockBasePx({ primer: false, attached: false })).toBe(46 + 12);
  });

  it("위치 프라이머가 뜨면 그만큼 독이 위로 자란다", () => {
    expect(dockBasePx({ primer: true, attached: false })).toBe(46 + 12 + 47);
  });

  it("첨부 배너가 붙으면 그만큼 더 두껍다", () => {
    expect(dockBasePx({ primer: false, attached: true })).toBe(46 + 12 + 73);
  });

  it("첨부 중에는 프라이머가 뜨지 않으므로 더하지 않는다", () => {
    expect(dockBasePx({ primer: true, attached: true })).toBe(
      dockBasePx({ primer: false, attached: true }),
    );
  });
});

describe("mapFitPadding", () => {
  it("시트가 덮는 만큼 아래를 비운다", () => {
    const pad = mapFitPadding({ safeTop: 59, dockHeight: 220 });

    expect(pad.bottom).toBe(220 + 24);
    expect(pad.top).toBe(59 + 96);
    expect(pad.left).toBe(40);
    expect(pad.right).toBe(40);
  });
});
