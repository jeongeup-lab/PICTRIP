import * as Location from "expo-location";

export type PermStatus = "granted" | "denied" | "undetermined";

export interface Coords {
  lat: number;
  lng: number;
}

function toStatus(s: Location.PermissionStatus | string): PermStatus {
  if (s === "granted") return "granted";
  if (s === "undetermined") return "undetermined";
  return "denied";
}

export async function getPermissionStatus(): Promise<PermStatus> {
  const { status } = await Location.getForegroundPermissionsAsync();
  return toStatus(status);
}

export async function requestPermission(): Promise<PermStatus> {
  const { status } = await Location.requestForegroundPermissionsAsync();
  return toStatus(status);
}

const GPS_TIMEOUT_MS = 8000;

export async function getCurrentCoords(): Promise<Coords | null> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    const pos = await Promise.race([
      Location.getCurrentPositionAsync(),
      new Promise<null>((resolve) => {
        timer = setTimeout(() => resolve(null), GPS_TIMEOUT_MS);
      }),
    ]);
    const fix = pos ?? (await Location.getLastKnownPositionAsync());
    return fix ? { lat: fix.coords.latitude, lng: fix.coords.longitude } : null;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}
