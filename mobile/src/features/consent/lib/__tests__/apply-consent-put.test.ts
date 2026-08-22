import { applyConsentPut } from "@/features/consent/lib/apply-consent-put";
import type { ConsentPutBody, ConsentState } from "@/features/consent/types";

const state = (over: Partial<ConsentState> = {}): ConsentState => ({
  locationConsent: false,
  termsVersion: "v1",
  consentedAt: "2026-01-01T00:00:00Z",
  aiTransferConsent: false,
  aiTransferVersion: null,
  aiTransferConsentedAt: null,
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
      aiTransferConsent: false,
      aiTransferVersion: null,
      aiTransferConsentedAt: null,
    });
  });

  it("flips the location consent while leaving consentedAt untouched", () => {
    const current = state({ locationConsent: true });
    expect(applyConsentPut(current, body({ locationConsent: false }))).toEqual({
      locationConsent: false,
      termsVersion: "v2",
      consentedAt: "2026-01-01T00:00:00Z",
      aiTransferConsent: false,
      aiTransferVersion: null,
      aiTransferConsentedAt: null,
    });
  });

  it("keeps the cross-border consent — the location PUT must not clear the evidence", () => {
    const granted = state({
      aiTransferConsent: true,
      aiTransferVersion: "2026-08-22",
      aiTransferConsentedAt: "2026-08-22T00:00:00Z",
    });

    const next = applyConsentPut(granted, body({ locationConsent: false }));

    expect(next.aiTransferConsent).toBe(true);
    expect(next.aiTransferVersion).toBe("2026-08-22");
    expect(next.aiTransferConsentedAt).toBe("2026-08-22T00:00:00Z");
  });
});
