import * as Location from "expo-location";
import { TERMS_VERSION } from "@/constants/legal";
import { getConsents, putConsents } from "@/features/consent/api";
import { buildConsentPut } from "@/features/consent/lib/build-consent-put";

/** Record implied consent at login (S01 §3): current terms version + a snapshot
 * of the OS location permission, while preserving the user's existing
 * photoConsent (P5 D6 — read-then-merge, no clobber). Never prompts.
 * Caller fires-and-forgets; failures are swallowed by the caller. */
export async function recordConsentSnapshot(): Promise<void> {
  const [current, perm] = await Promise.all([
    getConsents(),
    Location.getForegroundPermissionsAsync(),
  ]);
  await putConsents(buildConsentPut(current, perm.granted, TERMS_VERSION));
}
