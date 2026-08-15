import { useCallback, useEffect, useState } from "react";
import { getAiConsent, setAiConsent } from "@/lib/storage";

export function useAiConsent() {
  const [granted, setGranted] = useState(false);

  useEffect(() => {
    let active = true;
    void getAiConsent().then((stored) => {
      if (active) setGranted(stored);
    });
    return () => {
      active = false;
    };
  }, []);

  const grant = useCallback(async () => {
    await setAiConsent();
    setGranted(true);
  }, []);

  return { granted, grant };
}
