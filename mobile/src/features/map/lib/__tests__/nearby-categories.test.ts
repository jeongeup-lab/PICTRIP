import { CATEGORY_CHIPS } from "@/features/map/lib/nearby-categories";

describe("CATEGORY_CHIPS", () => {
  it("starts with 전체 mapped to null", () => {
    expect(CATEGORY_CHIPS[0]).toEqual({ label: "전체", value: null });
  });
  it("maps the five KTO buckets to backend NearbyCategory values", () => {
    const byLabel = Object.fromEntries(CATEGORY_CHIPS.map((c) => [c.label, c.value]));
    expect(byLabel["관광지"]).toBe("attraction");
    expect(byLabel["음식점"]).toBe("food");
    expect(byLabel["카페"]).toBe("cafe");
    expect(byLabel["레저"]).toBe("leisure");
    expect(byLabel["쇼핑"]).toBe("shopping");
  });
  it("has exactly six chips", () => {
    expect(CATEGORY_CHIPS).toHaveLength(6);
  });
});
