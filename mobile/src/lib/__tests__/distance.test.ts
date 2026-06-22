import { formatDistance } from "@/lib/distance";

describe("formatDistance", () => {
  it("renders sub-kilometer as integer metres", () => {
    expect(formatDistance(0)).toBe("0m");
    expect(formatDistance(999)).toBe("999m");
  });
  it("renders 1-10km as one decimal km", () => {
    expect(formatDistance(1000)).toBe("1.0km");
    expect(formatDistance(2500)).toBe("2.5km");
    expect(formatDistance(9999)).toBe("10.0km");
  });
  it("renders >=10km as integer km", () => {
    expect(formatDistance(10000)).toBe("10km");
    expect(formatDistance(23400)).toBe("23km");
  });
});
