import { formatViews } from "@/features/shorts/lib/format-views";

describe("formatViews", () => {
  it("keeps counts under 10k as plain numbers", () => {
    expect(formatViews(0)).toBe("0");
    expect(formatViews(9999)).toBe("9,999");
  });

  it("formats 만 with one decimal, trimming .0", () => {
    expect(formatViews(10_000)).toBe("1만");
    expect(formatViews(43_195)).toBe("4.3만");
    expect(formatViews(186_613)).toBe("18.7만");
  });

  it("formats 억", () => {
    expect(formatViews(120_000_000)).toBe("1.2억");
  });
});
