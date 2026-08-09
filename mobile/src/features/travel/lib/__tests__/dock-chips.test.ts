import { dockChips } from "@/features/travel/lib/dock-chips";

const labels = (chips: ReturnType<typeof dockChips>) =>
  chips.flatMap((c) => (c.kind === "query" ? [c.chip.label] : []));

describe("dockChips", () => {
  it("첫 화면은 사진 칩 뒤에 근처 세 갈래를 고정으로 낸다", () => {
    const chips = dockChips();

    expect(chips[0]).toEqual({ kind: "photo" });
    expect(labels(chips)).toEqual(["근처 카페", "근처 맛집", "근처 볼거리"]);
  });
});
