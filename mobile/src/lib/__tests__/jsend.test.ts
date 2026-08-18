import { unwrapData, envelopeToError } from "@/lib/jsend";
import { AppError } from "@/lib/app-error";

describe("unwrapData", () => {
  it("returns the data field on success", () => {
    const env = { data: { ok: true }, error: null, meta: { traceId: "t" } };
    expect(unwrapData(env)).toEqual({ ok: true });
  });
});

describe("envelopeToError", () => {
  it("builds an AppError from the error envelope", () => {
    const env = {
      data: null,
      error: { code: "RESOURCE_NOT_FOUND", message: "없음" },
      meta: { traceId: "t" },
    };
    const err = envelopeToError(env, 403);
    expect(err).toBeInstanceOf(AppError);
    expect(err.code).toBe("RESOURCE_NOT_FOUND");
    expect(err.status).toBe(403);
  });

  it("falls back to UNKNOWN when error payload is missing", () => {
    const env = { data: null, error: null, meta: { traceId: "t" } };
    const err = envelopeToError(env, 500);
    expect(err.code).toBe("UNKNOWN");
  });
});
