import type { ConsentPutBody, ConsentState } from "@/features/consent/types";

export function applyConsentPut(current: ConsentState, body: ConsentPutBody): ConsentState {
  return {
    ...current,
    locationConsent: body.locationConsent,
    photoConsent: body.photoConsent,
    termsVersion: body.termsVersion,
  };
}
