import type { ConsentPutBody, ConsentState } from "@/features/consent/types";

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
