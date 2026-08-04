import { extractsIntent, pendingSteps } from "@/features/travel/lib/pending-steps";

const shape = (over: Partial<Parameters<typeof pendingSteps>[0]> = {}) => ({
  request: "",
  intent: null,
  anchor: null,
  ...over,
});

describe("extractsIntent", () => {
  it("is true only when free text goes out without a prepared intent", () => {
    expect(extractsIntent(shape({ request: "사람 적은 바닷가" }))).toBe(true);
  });

  it("is false when the turn carries an intent the server can use as-is", () => {
    expect(extractsIntent(shape({ request: "사람 적은 바닷가", intent: {} }))).toBe(false);
  });

  it("is false for an anchor turn", () => {
    expect(extractsIntent(shape({ anchor: { action: "cafe" } }))).toBe(false);
  });

  it("is false for a photo-only turn that sends no text", () => {
    expect(extractsIntent(shape({ request: "   " }))).toBe(false);
  });
});

describe("pendingSteps", () => {
  it("names both stages when the question must be read first", () => {
    expect(pendingSteps(shape({ request: "제주에서 한적한 곳" })).map((s) => s.label)).toEqual([
      "질문에서 조건 읽는 중",
      "여행지 찾는 중",
    ]);
  });

  it("names only the search when no intent extraction happens", () => {
    expect(pendingSteps(shape({ intent: {} })).map((s) => s.label)).toEqual(["여행지 찾는 중"]);
  });

  it("carries no badge, since nothing is counted yet", () => {
    expect(pendingSteps(shape({ request: "계곡" })).every((s) => s.badge === null)).toBe(true);
  });
});
