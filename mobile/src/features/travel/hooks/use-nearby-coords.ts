import { useEffect, useState } from "react";
import {
  getCurrentCoords,
  getPermissionStatus,
  type Coords,
} from "@/features/map/usecases/request-location";

export type NearbyPhase = "checking" | "ready" | "unavailable";

export interface UseNearbyCoords {
  coords: Coords | null;
  phase: NearbyPhase;
}

export function useNearbyCoords(): UseNearbyCoords {
  const [coords, setCoords] = useState<Coords | null>(null);
  const [phase, setPhase] = useState<NearbyPhase>("checking");

  useEffect(() => {
    let alive = true;
    void (async () => {
      const status = await getPermissionStatus();
      if (!alive) return;
      if (status !== "granted") {
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
    })();
    return () => {
      alive = false;
    };
  }, []);

  return { coords, phase };
}
