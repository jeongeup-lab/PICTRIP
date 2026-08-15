export interface LatLng {
  lat: number;
  lng: number;
}

export interface Bounds {
  sw: LatLng;
  ne: LatLng;
}

const R = 6371000;
const rad = (d: number) => (d * Math.PI) / 180;

export function bboxFromCenter(c: LatLng, radiusM: number): Bounds {
  const dLat = radiusM / 111_320;
  const dLng = radiusM / (111_320 * Math.max(Math.cos(rad(c.lat)), 0.01));
  return {
    sw: { lat: c.lat - dLat, lng: c.lng - dLng },
    ne: { lat: c.lat + dLat, lng: c.lng + dLng },
  };
}

export function haversineMeters(a: LatLng, b: LatLng): number {
  const dLat = rad(b.lat - a.lat);
  const dLng = rad(b.lng - a.lng);
  const s =
    Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(s));
}
