import { buildConsentPut } from "@/features/consent/lib/build-consent-put";

describe("buildConsentPut", () => {
  it("uses the live OS grant for location and the given terms version", () => {
    expect(buildConsentPut(true, "2026-06-22")).toEqual({
      locationConsent: true,
      termsVersion: "2026-06-22",
    });
  });

  it("submits a denied OS grant as a withdrawn location consent", () => {
    expect(buildConsentPut(false, "2026-06-22")).toEqual({
      locationConsent: false,
      termsVersion: "2026-06-22",
    });
  });
});
