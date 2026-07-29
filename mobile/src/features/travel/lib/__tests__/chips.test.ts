import { ANCHOR_CHIPS, composerChips, idleChips, refineChips } from "@/features/travel/lib/chips";

describe("idleChips", () => {
  it("좌표가 없으면 거리 칩을 내지 않는다", () => {
    const labels = idleChips(false).map((c) => c.label);

    expect(labels).not.toContain("여기서 가까운 순");
    expect(labels).toContain("지금 열리는 축제");
  });

  it("좌표가 있으면 거리 칩이 맨 앞에 온다", () => {
    expect(idleChips(true)[0].label).toBe("여기서 가까운 순");
  });

  it("초기 칩은 전부 질문형이다", () => {
    expect(idleChips(true).every((c) => c.kind === "question")).toBe(true);
  });

  it("초기 칩은 빈 질문을 싣지 않는다", () => {
    for (const chip of idleChips(true)) {
      expect(chip.kind).toBe("question");
      if (chip.kind === "question") expect(chip.question.trim().length).toBeGreaterThan(0);
    }
  });

  it("초기 칩 질문은 백엔드 PRESET_INTENTS 키와 글자까지 같다", () => {
    const questions = idleChips(true).map((c) => (c.kind === "question" ? c.question : ""));

    expect(questions).toEqual([
      "여기서 가까운 곳",
      "지금 열리는 축제",
      "사람 적은 바닷가",
      "비 와도 갈 만한 실내",
      "제주에서 한적한 곳",
    ]);
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
    const chips = composerChips([{ label: "가까운 순으로", patch: { nearMe: true } }], true);

    expect(chips).toEqual([{ kind: "refine", label: "가까운 순으로", patch: { nearMe: true } }]);
  });

  it("제안이 비면 초기 칩으로 되돌아간다", () => {
    expect(composerChips([], false)).toEqual(idleChips(false));
    expect(composerChips(undefined, true)).toEqual(idleChips(true));
  });

  it("카드가 선택되면 제안 대신 앵커 칩을 쓴다", () => {
    const chips = composerChips([{ label: "실내만", patch: { indoorOnly: true } }], true, true);

    expect(chips).toEqual(ANCHOR_CHIPS);
    expect(chips.every((c) => c.kind === "anchor")).toBe(true);
  });
});
