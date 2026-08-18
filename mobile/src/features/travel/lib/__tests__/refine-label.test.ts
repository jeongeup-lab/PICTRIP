import { refineQuestion } from "@/features/travel/lib/refine-label";

it.each([
  ["indoor", "실내 조건 빼고 다시"],
  ["region", "지역 넓혀서 다시"],
  ["near", "근처 조건 빼고 다시"],
] as const)("%s 축을 빼면 사람 말로 남는다", (drop, expected) => {
  expect(refineQuestion({ drop })).toBe(expected);
});

it("축을 빼는 게 아니면 바뀌는 조건을 말한다", () => {
  expect(refineQuestion({ crowdPreference: "quiet" })).toBe("한적한 곳으로");
});
