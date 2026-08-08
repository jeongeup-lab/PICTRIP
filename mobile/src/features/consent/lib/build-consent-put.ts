import type { ConsentPutBody } from "@/features/consent/types";

export function buildConsentPut(osGranted: boolean, termsVersion: string): ConsentPutBody {
  return {
    locationConsent: osGranted,
    termsVersion,
  };
}
