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

/** Best-effort current GPS fix; null on failure. */
export async function getCurrentCoords(): Promise<Coords | null> {
  try {
    const pos = await Location.getCurrentPositionAsync();
    return { lat: pos.coords.latitude, lng: pos.coords.longitude };
  } catch {
    return null;
  }
}
