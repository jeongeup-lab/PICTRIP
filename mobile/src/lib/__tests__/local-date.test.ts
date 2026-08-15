import { calendarDaysSince, localDateLabel } from "@/lib/local-date";

describe("localDateLabel", () => {
  it("reads a UTC timestamp in the device timezone, not by cutting the string", () => {
    const label = localDateLabel("2026-03-14T18:30:00Z");
    const local = new Date("2026-03-14T18:30:00Z");
    const expected = `${local.getFullYear()}.${String(local.getMonth() + 1).padStart(2, "0")}.${String(
      local.getDate(),
    ).padStart(2, "0")}`;

    expect(label).toBe(expected);
  });

  it("gives back nothing when the server sent nothing usable", () => {
    expect(localDateLabel(null)).toBeNull();
    expect(localDateLabel("not-a-date")).toBeNull();
  });
});

describe("calendarDaysSince", () => {
  it("counts calendar days, so joining last night already reads 2 today", () => {
    const joined = new Date(2026, 7, 7, 23, 30);
    const now = new Date(2026, 7, 8, 0, 30).getTime();

    expect(calendarDaysSince(joined.toISOString(), now)).toBe(2);
  });

  it("stays at 1 for the whole joining day", () => {
    const joined = new Date(2026, 7, 8, 1, 0);
    const later = new Date(2026, 7, 8, 23, 59).getTime();

    expect(calendarDaysSince(joined.toISOString(), later)).toBe(1);
  });

  it("falls back to zero without a join date", () => {
    expect(calendarDaysSince(null, Date.now())).toBe(0);
    expect(calendarDaysSince("not-a-date", Date.now())).toBe(0);
  });
});
