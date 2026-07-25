import { DEFAULT_CONDITIONS } from "@/features/travel/api";
import {
  conditionChipLabel,
  isNeutral,
  NEUTRAL_CHIP_LABEL,
  REGION_OPTIONS,
  WHEN_OPTIONS,
  WHO_OPTIONS,
} from "@/features/travel/lib/condition-labels";

describe("conditionChipLabel", () => {
  it("falls back to the neutral label when nothing is narrowed", () => {
    expect(conditionChipLabel(DEFAULT_CONDITIONS)).toBe(NEUTRAL_CHIP_LABEL);
    expect(isNeutral(DEFAULT_CONDITIONS)).toBe(true);
  });

  it("drops the default values and joins the rest in sheet order", () => {
    expect(conditionChipLabel({ region: "capital", when: "weekend", who: "any" })).toBe(
      "수도권 · 이번 주말",
    );
  });

  it("keeps a single narrowed group on its own", () => {
    expect(conditionChipLabel({ region: "all", when: "any", who: "pets" })).toBe("반려견과");
    expect(isNeutral({ region: "all", when: "any", who: "pets" })).toBe(false);
  });

  it("joins all three groups", () => {
    expect(conditionChipLabel({ region: "jeju", when: "today", who: "kids" })).toBe(
      "제주 · 오늘 · 아이와",
    );
  });
});

describe("condition options", () => {
  it("starts each group with the API default value", () => {
    expect(REGION_OPTIONS[0].value).toBe(DEFAULT_CONDITIONS.region);
    expect(WHEN_OPTIONS[0].value).toBe(DEFAULT_CONDITIONS.when);
    expect(WHO_OPTIONS[0].value).toBe(DEFAULT_CONDITIONS.who);
  });
});
