import { useCallback, useEffect, useState } from "react";
import { getAiOptOut, setAiOptOut } from "@/lib/storage";

export function useAiOptOut() {
  const [optedOut, setOptedOut] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let active = true;
    void getAiOptOut().then((stored) => {
      if (!active) return;
      setOptedOut(stored);
      setLoaded(true);
    });
    return () => {
      active = false;
    };
  }, []);

  const change = useCallback(async (next: boolean) => {
    setOptedOut(next);
    await setAiOptOut(next);
  }, []);

  return { optedOut, loaded, change };
}
