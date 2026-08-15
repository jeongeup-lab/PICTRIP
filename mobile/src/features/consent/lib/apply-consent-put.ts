import type { ConsentPutBody, ConsentState } from "@/features/consent/types";

export function applyConsentPut(current: ConsentState, body: ConsentPutBody): ConsentState {
  return {
    ...current,
    locationConsent: body.locationConsent,
    termsVersion: body.termsVersion,
  };
}
