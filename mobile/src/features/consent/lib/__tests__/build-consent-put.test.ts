import { buildConsentPut } from "@/features/consent/lib/build-consent-put";
import type { ConsentState } from "@/features/consent/types";

const state = (over: Partial<ConsentState> = {}): ConsentState => ({
  locationConsent: false,
  photoConsent: false,
  termsVersion: null,
  consentedAt: null,
  ...over,
});

describe("buildConsentPut", () => {
  it("uses the live OS grant for location and the given terms version", () => {
    expect(buildConsentPut(state(), true, "2026-06-22")).toEqual({
      locationConsent: true,
      photoConsent: false,
      termsVersion: "2026-06-22",
    });
  });

  it("preserves the current photoConsent (no clobber)", () => {
    expect(buildConsentPut(state({ photoConsent: true }), false, "2026-06-22").photoConsent).toBe(
      true,
    );
  });
});
