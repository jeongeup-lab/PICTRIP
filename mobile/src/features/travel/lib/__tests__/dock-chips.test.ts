import { dockChips } from "@/features/travel/lib/dock-chips";

const labels = (chips: ReturnType<typeof dockChips>) =>
  chips.flatMap((c) => (c.kind === "query" ? [c.chip.label] : []));

describe("dockChips", () => {
  it("첫 화면은 사진 칩 없이 근처 세 갈래와 테마 두 갈래를 낸다", () => {
    const chips = dockChips();

    expect(chips.every((c) => c.kind === "query")).toBe(true);
    expect(labels(chips)).toEqual([
      "근처 카페",
      "근처 맛집",
      "근처 볼거리",
      "한적한 자연",
      "실내 나들이",
    ]);
  });
});
