import { api } from "@/lib/api-client";
import type { SpotDetail, NearbySpot } from "@/lib/api-types";

export async function getSpot(contentId: string): Promise<SpotDetail> {
  return (await api.get(`/spots/${contentId}`)) as unknown as SpotDetail;
}

export async function getNearby(lat: number, lng: number): Promise<NearbySpot[]> {
  return (await api.get("/map/nearby", {
    params: { lat, lng, radius: 3000 },
  })) as unknown as NearbySpot[];
}
