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
  perm: MapInitPhase;
  allow: () => Promise<void>;
  skipToSeoul: () => void;
  recenter: () => Promise<void>;
}

export function useMapInit(): UseMapInit {
  const s = useMapStore();
  const [perm, setPerm] = useState<MapInitPhase>("undetermined");
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    (async () => {
      if (s.center != null) {
        setPerm("ready");
        if (s.gpsCoords == null && (await getPermissionStatus()) === "granted") {
          const c = await getCurrentCoords();
          if (c) s.setGpsCoords(c);
        }
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
