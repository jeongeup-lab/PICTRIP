import * as Location from "expo-location";
import { api } from "@/lib/api-client";
import { TERMS_VERSION } from "@/constants/legal";

/** Record implied consent at login (S01 §3): current terms version + a snapshot
 * of the OS location permission. Never prompts. Caller fires-and-forgets. */
export async function recordConsentSnapshot(): Promise<void> {
  const perm = await Location.getForegroundPermissionsAsync();
  await api.put("/users/me/consents", {
    locationConsent: perm.granted,
    photoConsent: false,
    termsVersion: TERMS_VERSION,
  });
}
