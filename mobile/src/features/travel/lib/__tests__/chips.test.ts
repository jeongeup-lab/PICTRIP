import { ANCHOR_CHIPS, anchorChips, idleChips, refineChips } from "@/features/travel/lib/chips";

describe("idleChips", () => {
  it("거리 칩은 더 이상 칩 레일에 있지 않다", () => {
    const labels = idleChips().map((c) => c.label);

    expect(labels).not.toContain("내 근처");
    expect(labels).toContain("지금 축제");
  });

  it("좌표가 없으면 위치가 필요 없는 칩만 낸다", () => {
    expect(idleChips(false).some((c) => c.kind === "anchor")).toBe(false);
  });

  it("좌표가 있으면 근처 칩이 앞에 오고 즐길거리는 넣지 않는다", () => {
    const labels = idleChips(true).map((c) => c.label);

    expect(labels).toEqual(["근처 맛집", "근처 볼거리", "근처 카페", "지금 축제"]);
    expect(labels).not.toContain("근처 즐길거리");
  });

  it("좌표가 있는 초기 칩은 한 개도 Gemini를 태우지 않는다", () => {
    expect(idleChips(true).every((c) => c.kind === "anchor" || c.kind === "intent")).toBe(true);
  });

  it("질문형 칩은 빈 질문을 싣지 않는다", () => {
    for (const chip of idleChips()) {
      if (chip.kind === "question") expect(chip.question.trim().length).toBeGreaterThan(0);
    }
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

describe("anchorChips", () => {
  it("혼잡도 데이터가 없는 카드에서는 '오늘 붐벼?'를 내리지 않는다", () => {
    const labels = anchorChips(false).map((chip) => chip.label);
    expect(labels).not.toContain("오늘 붐벼?");
    expect(labels).toContain("맛집");
  });

  it("혼잡도가 있으면 네 칩을 모두 보여준다", () => {
    const chips = anchorChips(true);

    expect(chips).toEqual(ANCHOR_CHIPS);
    expect(chips.map((chip) => chip.label)).toContain("오늘 붐벼?");
    expect(chips).toHaveLength(4);
  });
});

describe("근처 볼거리 경로", () => {
  it("앵커가 아니라 intent 로 보낸다 — 3km 반경에 갇히지 않는다", () => {
    const chip = idleChips(true).find((c) => c.label === "근처 볼거리");

    expect(chip?.kind).toBe("intent");
    if (chip?.kind === "intent") expect(chip.intent.nearMe).toBe(true);
  });

  it("맛집·카페만 앵커다 — 여행 후보 풀에 FD 가 없어서다", () => {
    const anchors = idleChips(true).filter((c) => c.kind === "anchor");

    expect(anchors.map((c) => c.label)).toEqual(["근처 맛집", "근처 카페"]);
  });
});
