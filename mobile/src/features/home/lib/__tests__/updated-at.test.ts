import { formatUpdatedAt } from "@/features/home/lib/updated-at";

const NOW = 1_760_000_000_000;

describe("formatUpdatedAt", () => {
  it("returns null before the first fetch lands", () => {
    expect(formatUpdatedAt(0, NOW)).toBeNull();
  });

  it("reads under a minute as 방금 전", () => {
    expect(formatUpdatedAt(NOW - 59_000, NOW)).toBe("방금 전 업데이트");
  });

  it("floors minutes", () => {
    expect(formatUpdatedAt(NOW - 9 * 60_000 - 30_000, NOW)).toBe("9분 전 업데이트");
  });

  it("switches to hours past 60 minutes", () => {
    expect(formatUpdatedAt(NOW - 125 * 60_000, NOW)).toBe("2시간 전 업데이트");
  });

  it("clamps a clock that ran backwards to 방금 전", () => {
    expect(formatUpdatedAt(NOW + 5_000, NOW)).toBe("방금 전 업데이트");
  });
});
