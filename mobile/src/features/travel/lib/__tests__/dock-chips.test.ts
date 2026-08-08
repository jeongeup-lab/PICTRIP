import type { TravelSpot } from "@/features/travel/api";
import { dockChips } from "@/features/travel/lib/dock-chips";

const spot: TravelSpot = {
  contentId: "1",
  title: "성산일출봉",
  regionLabel: "서귀포시",
  imageUrl: null,
  tag: "한산",
  lat: 33.4,
  lng: 126.9,
  hasCrowd: true,
};

const base = { answer: null, focused: null, expanded: false, hasCoords: false, hasCrowd: false };

describe("dockChips", () => {
  it("사진 칩은 항상 맨 앞에 있다", () => {
    expect(dockChips(base)[0]).toEqual({ kind: "photo" });
    expect(dockChips({ ...base, focused: spot })[0]).toEqual({ kind: "photo" });
  });

  it("보고 있는 카드가 없으면 초기 칩을 낸다", () => {
    const labels = dockChips({ ...base, hasCoords: true }).flatMap((c) =>
      c.kind === "query" ? [c.chip.label] : [],
    );

    expect(labels).toContain("근처 맛집");
  });

  it("보고 있는 카드가 있으면 문맥 칩이 사진 칩 다음에 온다", () => {
    const chips = dockChips({ ...base, focused: spot });

    expect(chips[1]).toEqual({ kind: "context", title: "성산일출봉", expanded: false });
  });

  it("펼치면 사진 칩이 빠지고 문맥 칩 뒤에 술어만 온다", () => {
    const chips = dockChips({ ...base, focused: spot, expanded: true, hasCrowd: true });

    expect(chips[0]).toEqual({ kind: "context", title: "성산일출봉", expanded: true });
    expect(chips.slice(1).map((c) => (c.kind === "query" ? c.chip.label : ""))).toEqual([
      "맛집",
      "카페",
      "볼거리",
      "오늘 붐벼?",
    ]);
  });

  it("혼잡도를 모르는 곳에는 붐빔 술어를 내지 않는다", () => {
    const chips = dockChips({ ...base, focused: spot, expanded: true, hasCrowd: false });

    expect(chips.map((c) => (c.kind === "query" ? c.chip.label : ""))).not.toContain("오늘 붐벼?");
  });

  it("접힌 상태에서는 문맥 칩 뒤에 refine 칩이 붙는다", () => {
    const chips = dockChips({
      ...base,
      focused: spot,
      answer: {
        totalCount: 8,
        refinements: [{ label: "사람 적은 곳만", patch: { crowdPreference: "quiet" } }],
      },
    });

    expect(chips.map((c) => (c.kind === "query" ? c.chip.label : ""))).toContain("사람 적은 곳만");
  });

  it("펼침은 보고 있는 카드가 있을 때만 성립한다", () => {
    expect(dockChips({ ...base, expanded: true })[0]).toEqual({ kind: "photo" });
  });
});
