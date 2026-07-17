import * as Location from "expo-location";
import { TERMS_VERSION } from "@/constants/legal";
import { getConsents, putConsents } from "@/features/consent/api";
import { buildConsentPut } from "@/features/consent/lib/build-consent-put";

export async function recordConsentSnapshot(): Promise<void> {
  const [current, perm] = await Promise.all([
    getConsents(),
    Location.getForegroundPermissionsAsync(),
  ]);
  await putConsents(buildConsentPut(current, perm.granted, TERMS_VERSION));
}
