import { applyConsentPut } from "@/features/consent/lib/apply-consent-put";
import type { ConsentPutBody, ConsentState } from "@/features/consent/types";

const state = (over: Partial<ConsentState> = {}): ConsentState => ({
  locationConsent: false,
  termsVersion: "v1",
  consentedAt: "2026-01-01T00:00:00Z",
  ...over,
});

const body = (over: Partial<ConsentPutBody> = {}): ConsentPutBody => ({
  locationConsent: true,
  termsVersion: "v2",
  ...over,
});

describe("applyConsentPut", () => {
  it("overlays the two submitted fields and preserves consentedAt", () => {
    expect(applyConsentPut(state(), body())).toEqual({
      locationConsent: true,
      termsVersion: "v2",
      consentedAt: "2026-01-01T00:00:00Z",
    });
  });

  it("flips the location consent while leaving consentedAt untouched", () => {
    const current = state({ locationConsent: true });
    expect(applyConsentPut(current, body({ locationConsent: false }))).toEqual({
      locationConsent: false,
      termsVersion: "v2",
      consentedAt: "2026-01-01T00:00:00Z",
    });
  });
});
