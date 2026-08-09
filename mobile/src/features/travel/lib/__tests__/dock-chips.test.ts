import type { TravelSpot } from "@/features/travel/api";
import { dockChips, panelChips } from "@/features/travel/lib/dock-chips";

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

const labels = (chips: ReturnType<typeof dockChips>) =>
  chips.flatMap((c) => (c.kind === "query" ? [c.chip.label] : []));

describe("dockChips", () => {
  it("첫 화면은 사진 칩 뒤에 근처 세 갈래를 고정으로 낸다", () => {
    const chips = dockChips();

    expect(chips[0]).toEqual({ kind: "photo" });
    expect(labels(chips)).toEqual(["근처 카페", "근처 맛집", "근처 볼거리"]);
  });
});

describe("panelChips", () => {
  const base = { answer: null, focused: null, hasCrowd: false };

  it("사진 칩은 패널에서도 맨 앞에 남는다", () => {
    expect(panelChips(base)[0]).toEqual({ kind: "photo" });
    expect(panelChips({ ...base, focused: spot })[0]).toEqual({ kind: "photo" });
  });

  it("보고 있는 카드 이름을 칩마다 붙인다", () => {
    expect(labels(panelChips({ ...base, focused: spot }))).toEqual([
      "성산일출봉 근처 카페",
      "성산일출봉 근처 맛집",
      "성산일출봉 근처 볼거리",
    ]);
  });

  it("혼잡도를 아는 카드에만 붐빔 칩을 더한다", () => {
    expect(labels(panelChips({ ...base, focused: spot, hasCrowd: true }))).toContain(
      "성산일출봉 오늘 붐벼?",
    );
  });

  it("카드가 없으면 문맥 칩도 없다 — 이름을 붙일 곳이 없어서다", () => {
    expect(labels(panelChips(base))).toEqual([]);
  });

  it("서버 제안은 문맥 칩 뒤에 붙는다", () => {
    const chips = panelChips({
      ...base,
      focused: spot,
      answer: {
        totalCount: 8,
        refinements: [{ label: "사람 적은 곳만", patch: { crowdPreference: "quiet" } }],
      },
    });

    expect(labels(chips).at(-1)).toBe("사람 적은 곳만");
  });
});
