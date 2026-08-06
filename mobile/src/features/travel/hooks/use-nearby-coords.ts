import { useCallback, useEffect, useState } from "react";
import {
  getCurrentCoords,
  getPermissionStatus,
  requestPermission,
  type Coords,
} from "@/features/map/usecases/request-location";

export type NearbyPhase = "checking" | "ready" | "unavailable";

export interface UseNearbyCoords {
  coords: Coords | null;
  phase: NearbyPhase;
  askable: boolean;
  ask: () => Promise<boolean>;
}

export function useNearbyCoords(): UseNearbyCoords {
  const [coords, setCoords] = useState<Coords | null>(null);
  const [phase, setPhase] = useState<NearbyPhase>("checking");
  const [askable, setAskable] = useState(false);

  useEffect(() => {
    let alive = true;
    void (async () => {
      try {
        const status = await getPermissionStatus();
        if (!alive) return;
        if (status !== "granted") {
          setAskable(status === "undetermined");
          setPhase("unavailable");
          return;
        }
        const fix = await getCurrentCoords();
        if (!alive) return;
        if (fix) {
          setCoords(fix);
          setPhase("ready");
        } else {
          setPhase("unavailable");
        }
      } catch {
        if (alive) {
          setAskable(false);
          setPhase("unavailable");
        }
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  const ask = useCallback(async () => {
    setAskable(false);
    try {
      const status = await requestPermission();
      if (status !== "granted") {
        setPhase("unavailable");
        return false;
      }
      const fix = await getCurrentCoords();
      if (!fix) {
        setPhase("unavailable");
        return false;
      }
      setCoords(fix);
      setPhase("ready");
      return true;
    } catch {
      setPhase("unavailable");
      return false;
    }
  }, []);

  return { coords, phase, askable, ask };
}
