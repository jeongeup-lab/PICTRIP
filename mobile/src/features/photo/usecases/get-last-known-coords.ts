import * as Location from "expo-location";

export interface Coords {
  lat: number;
  lng: number;
}

/** Read an already-granted last-known position. NEVER requests permission
 * (S04: photo search must not trigger a location prompt). Returns null when
 * permission is not granted or there is no cached fix. */
export async function getLastKnownCoords(): Promise<Coords | null> {
  const perm = await Location.getForegroundPermissionsAsync();
  if (!perm.granted) return null;
  const pos = await Location.getLastKnownPositionAsync();
  if (!pos) return null;
  return { lat: pos.coords.latitude, lng: pos.coords.longitude };
}
