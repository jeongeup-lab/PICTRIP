import { useEffect, useRef, useState } from "react";
import { useMapStore } from "@/features/map/stores/map-store";
import {
  getPermissionStatus,
  requestPermission,
  getCurrentCoords,
  type PermStatus,
} from "@/features/map/usecases/request-location";
import { SEOUL_CITY_HALL } from "@/constants/map";

export type MapInitPhase = PermStatus | "ready";

export interface UseMapInit {
  /** Current permission/init phase that drives the primer-vs-map render. */
  perm: MapInitPhase;
  /** Priming "위치 허용하기" — prompts, then GPS-anchors or marks denied. */
  allow: () => Promise<void>;
  /** Skip the primer with the Seoul fallback center. */
  skipToSeoul: () => void;
  /** Recenter FAB — reuse the existing GPS fix or re-check permission. */
  recenter: () => Promise<void>;
}

/**
 * Permission → GPS → fallback state machine for the map tab (S05 §1.4).
 *
 * Hardened behaviors preserved verbatim:
 * - first-mount guard (`started` ref) so the entry effect runs once,
 * - on re-entry the surviving map-store center short-circuits to "ready"
 *   BEFORE calling getPermissionStatus (no GPS re-fetch, no primer flash, no
 *   stale-center flash),
 * - no-prompt model: entry/recenter use getPermissionStatus (which wraps
 *   getForegroundPermissionsAsync) and never auto-prompt on mount.
 */
export function useMapInit(): UseMapInit {
  const s = useMapStore();
  const [perm, setPerm] = useState<MapInitPhase>("undetermined");
  const started = useRef(false);

  // Entry: branch on permission status (S05 §1.4).
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    (async () => {
      // map-store survives tab switches; if a center is already set, this is a
      // re-entry — mark ready without re-running the permission/GPS branch (no
      // GPS re-fetch, no primer flash, no stale-center flash).
      if (s.center != null) {
        setPerm("ready");
        return;
      }
      const status = await getPermissionStatus();
      if (status === "granted") {
        const c = (await getCurrentCoords()) ?? SEOUL_CITY_HALL;
        s.setAnchor(c, "gps", c);
        setPerm("ready");
      } else {
        setPerm(status);
      }
    })();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const allow = async () => {
    const status = await requestPermission();
    if (status === "granted") {
      const c = (await getCurrentCoords()) ?? SEOUL_CITY_HALL;
      s.setAnchor(c, "gps", c);
      setPerm("ready");
    } else {
      setPerm("denied");
    }
  };

  const skipToSeoul = () => {
    s.setAnchor(SEOUL_CITY_HALL, "pan", null);
    setPerm("ready");
  };

  const recenter = async () => {
    if (s.gpsCoords) s.recenterToGps();
    else {
      const status = await getPermissionStatus();
      setPerm(status === "granted" ? "ready" : status);
      if (status === "granted") {
        const c = (await getCurrentCoords()) ?? SEOUL_CITY_HALL;
        s.setAnchor(c, "gps", c);
      }
    }
  };

  return { perm, allow, skipToSeoul, recenter };
}
