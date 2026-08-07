import { useCallback } from "react";
import * as Location from "expo-location";
import { useFocusEffect } from "expo-router";
import { buildConsentPut } from "@/features/consent/lib/build-consent-put";
import { useUpdateConsent } from "@/features/consent/queries";
import type { ConsentState } from "@/features/consent/types";
import { TERMS_VERSION } from "@/constants/legal";

export function useLocationConsentSync(data: ConsentState | undefined) {
  const update = useUpdateConsent();

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      void (async () => {
        if (!data) return;
        const perm = await Location.getForegroundPermissionsAsync();
        if (!cancelled && perm.granted !== data.locationConsent) {
          update.mutate(buildConsentPut(data, perm.granted, data.termsVersion ?? TERMS_VERSION));
        }
      })();
      return () => {
        cancelled = true;
      };
    }, [data, update]),
  );
}
