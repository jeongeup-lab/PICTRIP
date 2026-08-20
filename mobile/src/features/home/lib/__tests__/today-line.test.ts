import { scopeTitle, todayLine } from "@/features/home/lib/today-line";

describe("todayLine", () => {
  it("names the day and the region", () => {
    expect(todayLine("서울 중구", new Date(2026, 7, 21))).toBe("8월 21일 금 · 서울 중구");
  });

  it("drops the separator until the reverse geocode lands", () => {
    expect(todayLine(null, new Date(2026, 7, 21))).toBe("8월 21일 금");
  });
});

describe("scopeTitle", () => {
  it("says which range the ranking is showing", () => {
    expect(scopeTitle("nearby")).toBe("오늘, 이 근처");
    expect(scopeTitle("national")).toBe("오늘, 전국");
  });
});
