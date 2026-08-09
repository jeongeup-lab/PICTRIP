import { idleChips } from "@/features/travel/lib/chips";

describe("idleChips", () => {
  it("첫 화면 칩은 근처 세 갈래로 고정이다", () => {
    expect(idleChips().map((c) => c.label)).toEqual(["근처 카페", "근처 맛집", "근처 볼거리"]);
  });

  it("좌표 유무가 초기 칩을 바꾸지 않는다 — 위치는 누른 뒤에 묻는다", () => {
    expect(idleChips()).toBe(idleChips());
  });

  it("초기 칩은 한 개도 Gemini를 태우지 않는다", () => {
    expect(idleChips().every((c) => c.kind === "anchor" || c.kind === "intent")).toBe(true);
  });
});

describe("근처 볼거리 경로", () => {
  it("내 위치 볼거리는 intent 다 — 3km 앵커 반경에 갇히지 않는다", () => {
    const chip = idleChips().find((c) => c.label === "근처 볼거리");

    expect(chip?.kind).toBe("intent");
    if (chip?.kind === "intent") expect(chip.intent.nearMe).toBe(true);
  });

  it("맛집·카페만 앵커다 — 여행 후보 풀에 FD 가 없어서다", () => {
    const anchors = idleChips().filter((c) => c.kind === "anchor");

    expect(anchors.map((c) => c.label)).toEqual(["근처 카페", "근처 맛집"]);
  });
});
