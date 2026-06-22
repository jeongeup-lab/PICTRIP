import { isAppError4xx } from "@/lib/query-client";
import { AppError } from "@/lib/app-error";

describe("query retry predicate", () => {
  it("does not retry 4xx AppErrors", () => {
    expect(isAppError4xx(new AppError("GUEST_FORBIDDEN", "x", 403))).toBe(true);
  });
  it("allows retry for 5xx", () => {
    expect(isAppError4xx(new AppError("INTERNAL_ERROR", "x", 500))).toBe(false);
  });
  it("allows retry for network errors", () => {
    expect(isAppError4xx(new AppError("NETWORK_ERROR", "x", 0))).toBe(false);
  });
});
