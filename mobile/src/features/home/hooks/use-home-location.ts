import { useCallback, useEffect, useState } from "react";
import {
  getCurrentCoords,
  getPermissionStatus,
  requestPermission,
  type Coords,
  type PermStatus,
} from "@/features/map/usecases/request-location";

export interface HomeLocation {
  coords: Coords | null;
  status: PermStatus | "resolving";
  request: () => Promise<void>;
}

export function useHomeLocation(): HomeLocation {
  const [coords, setCoords] = useState<Coords | null>(null);
  const [status, setStatus] = useState<PermStatus | "resolving">("resolving");

  useEffect(() => {
    let alive = true;
    void (async () => {
      const perm = await getPermissionStatus();
      if (!alive) return;
      if (perm !== "granted") {
        setStatus(perm);
        return;
      }
      const fix = await getCurrentCoords();
      if (!alive) return;
      setCoords(fix);
      setStatus(fix ? "granted" : "denied");
    })();
    return () => {
      alive = false;
    };
  }, []);

  const request = useCallback(async () => {
    const perm = await requestPermission();
    if (perm !== "granted") {
      setStatus(perm);
      return;
    }
    const fix = await getCurrentCoords();
    setCoords(fix);
    setStatus(fix ? "granted" : "denied");
  }, []);

  return { coords, status, request };
}
