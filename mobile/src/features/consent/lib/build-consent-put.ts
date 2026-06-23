import type { ConsentPutBody, ConsentState } from "@/features/consent/types";

/** Build a complete PUT body, preserving the server's current photoConsent and
 * setting location from the live OS grant + the supplied terms version. */
export function buildConsentPut(
  current: ConsentState,
  osGranted: boolean,
  termsVersion: string,
): ConsentPutBody {
  return {
    locationConsent: osGranted,
    photoConsent: current.photoConsent,
    termsVersion,
  };
}
