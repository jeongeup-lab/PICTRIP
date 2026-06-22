import type { ConsentPutBody, ConsentState } from "@/features/consent/types";

/** Apply an in-flight PUT body onto the cached consent state for an optimistic
 * update — overlays the three submitted fields, leaving consentedAt untouched
 * (the server stamps it; the echo from onSuccess will correct it). */
export function applyConsentPut(current: ConsentState, body: ConsentPutBody): ConsentState {
  return {
    ...current,
    locationConsent: body.locationConsent,
    photoConsent: body.photoConsent,
    termsVersion: body.termsVersion,
  };
}
