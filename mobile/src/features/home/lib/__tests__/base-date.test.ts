import { formatBaseDate } from "@/features/home/lib/base-date";

describe("formatBaseDate", () => {
  it("renders the concentration snapshot date, not a fetch time", () => {
    expect(formatBaseDate("2026-08-11")).toBe("8월 11일 기준");
  });

  it("drops the leading zeros", () => {
    expect(formatBaseDate("2026-01-05")).toBe("1월 5일 기준");
  });

  it("returns null when the server sends nothing usable", () => {
    expect(formatBaseDate(null)).toBeNull();
    expect(formatBaseDate(undefined)).toBeNull();
    expect(formatBaseDate("")).toBeNull();
    expect(formatBaseDate("2026-08")).toBeNull();
  });
});
