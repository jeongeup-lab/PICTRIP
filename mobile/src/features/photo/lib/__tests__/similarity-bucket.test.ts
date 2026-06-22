import { bucketFor } from "@/features/photo/lib/similarity-bucket";

describe("bucketFor", () => {
  it("labels >=0.75 as 매우 닮음 with full tier", () => {
    expect(bucketFor(0.9)).toEqual({ label: "매우 닮음", tier: 1 });
    expect(bucketFor(0.75)).toEqual({ label: "매우 닮음", tier: 1 });
  });
  it("labels >=0.65 and <0.75 as 닮음", () => {
    expect(bucketFor(0.7).label).toBe("닮음");
    expect(bucketFor(0.7).tier).toBeCloseTo(0.66);
  });
  it("labels <0.65 as 비슷함", () => {
    expect(bucketFor(0.5).label).toBe("비슷함");
    expect(bucketFor(0.5).tier).toBeCloseTo(0.33);
  });
});
