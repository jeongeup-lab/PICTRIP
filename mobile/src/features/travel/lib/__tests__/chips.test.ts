import {
  ANCHOR_CHIPS,
  composerChips,
  idleChips,
  NEARBY_CHIP,
  refineChips,
} from "@/features/travel/lib/chips";

describe("idleChips", () => {
  it("거리 칩은 더 이상 칩 레일에 있지 않다", () => {
    const labels = idleChips().map((c) => c.label);

    expect(labels).not.toContain(NEARBY_CHIP.label);
    expect(labels).toContain("지금 열리는 축제");
  });

  it("초기 칩은 전부 질문형이다", () => {
    expect(idleChips().every((c) => c.kind === "question")).toBe(true);
  });

  it("초기 칩은 빈 질문을 싣지 않는다", () => {
    for (const chip of idleChips()) {
      expect(chip.kind).toBe("question");
      if (chip.kind === "question") expect(chip.question.trim().length).toBeGreaterThan(0);
    }
  });
});

describe("NEARBY_CHIP", () => {
  it("컴포저 액션 행이 쓰는 질문형 칩이다", () => {
    expect(NEARBY_CHIP.kind).toBe("question");
    if (NEARBY_CHIP.kind === "question") expect(NEARBY_CHIP.question).toBe("여기서 가까운 곳");
  });
});

describe("refineChips", () => {
  it("서버 제안은 patch 칩으로 바뀐다", () => {
    const chips = refineChips([{ label: "실내만", patch: { indoorOnly: true } }]);

    expect(chips).toEqual([{ kind: "refine", label: "실내만", patch: { indoorOnly: true } }]);
  });

  it("제안이 통째로 빠진 응답에도 빈 목록을 낸다", () => {
    expect(refineChips(undefined)).toEqual([]);
    expect(refineChips(null)).toEqual([]);
  });
});

describe("composerChips", () => {
  it("제안이 있으면 refine 칩을 쓴다", () => {
    const chips = composerChips([{ label: "가까운 순으로", patch: { nearMe: true } }]);

    expect(chips).toEqual([{ kind: "refine", label: "가까운 순으로", patch: { nearMe: true } }]);
  });

  it("제안이 비면 초기 칩으로 되돌아간다", () => {
    expect(composerChips([])).toEqual(idleChips());
    expect(composerChips(undefined)).toEqual(idleChips());
  });

  it("카드가 선택되면 제안 대신 앵커 칩을 쓴다", () => {
    const chips = composerChips([{ label: "실내만", patch: { indoorOnly: true } }], {
      hasCrowd: true,
    });

    expect(chips).toEqual(ANCHOR_CHIPS);
    expect(chips.every((c) => c.kind === "anchor")).toBe(true);
  });
});

describe("anchorChips", () => {
  it("혼잡도 데이터가 없는 카드에서는 '오늘 붐벼?'를 내리지 않는다", () => {
    const labels = composerChips(null, { hasCrowd: false }).map((chip) => chip.label);
    expect(labels).not.toContain("오늘 붐벼?");
    expect(labels).toContain("근처 맛집");
  });

  it("혼잡도가 있으면 네 칩을 모두 보여준다", () => {
    const labels = composerChips(null, { hasCrowd: true }).map((chip) => chip.label);
    expect(labels).toContain("오늘 붐벼?");
    expect(labels).toHaveLength(4);
  });

  it("hasCrowd 가 없는 응답은 보수적으로 숨긴다", () => {
    expect(composerChips(null, {}).map((chip) => chip.label)).not.toContain("오늘 붐벼?");
  });
});
