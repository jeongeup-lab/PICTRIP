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

/** Read current permission without prompting (S05 entry branch). */
export async function getPermissionStatus(): Promise<PermStatus> {
  const { status } = await Location.getForegroundPermissionsAsync();
  return toStatus(status);
}

/** Prompt for permission (priming "위치 허용하기"). */
export async function requestPermission(): Promise<PermStatus> {
  const { status } = await Location.requestForegroundPermissionsAsync();
  return toStatus(status);
}

// getCurrentPositionAsync has no timeout of its own — a slow first fix (iOS
// cold start indoors) can hang tens of seconds, keeping the primer/"위치 확인 중"
// on screen. Cap the wait and fall back to the OS's last known position.
const GPS_TIMEOUT_MS = 8000;

/** Best-effort current GPS fix; last-known position on timeout, null on failure. */
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
