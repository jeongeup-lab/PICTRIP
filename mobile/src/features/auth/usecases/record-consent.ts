import * as Location from "expo-location";
import { TERMS_VERSION } from "@/constants/legal";
import { putConsents } from "@/features/consent/api";
import { buildConsentPut } from "@/features/consent/lib/build-consent-put";

export async function recordConsentSnapshot(): Promise<void> {
  const perm = await Location.getForegroundPermissionsAsync();
  await putConsents(buildConsentPut(perm.granted, TERMS_VERSION));
}
