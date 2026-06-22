export interface LatLng {
  lat: number;
  lng: number;
}

const R = 6371000; // earth radius, metres
const rad = (d: number) => (d * Math.PI) / 180;

/** Great-circle distance in metres between two coordinates. */
export function haversineMeters(a: LatLng, b: LatLng): number {
  const dLat = rad(b.lat - a.lat);
  const dLng = rad(b.lng - a.lng);
  const s =
    Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(s));
}
