import type { RefinePatch } from "@/features/travel/api";

const DROPPED: Record<string, string> = {
  region: "지역 넓혀서 다시",
  category: "종류 상관없이 다시",
  indoor: "실내 조건 빼고 다시",
  crowd: "혼잡도 상관없이 다시",
  near: "근처 조건 빼고 다시",
};

export function refineQuestion(patch: RefinePatch): string {
  if (patch.drop && DROPPED[patch.drop]) return DROPPED[patch.drop];
  if (patch.crowdPreference === "quiet") return "한적한 곳으로";
  if (patch.crowdPreference === "popular") return "유명한 곳으로";
  if (patch.indoorOnly) return "실내로";
  if (patch.nearMe) return "내 근처로";
  return "조건 바꿔서 다시";
}
