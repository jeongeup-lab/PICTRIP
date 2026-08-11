import { api } from "@/lib/api-client";

export interface HomeSpotCard {
  contentId: string;
  title: string;
  regionLabel: string;
  imageUrl: string | null;
  rank: number | null;
  dist: number | null;
  category: string | null;
  tag: string | null;
  anchorTitle: string | null;
}

export interface HomeCards {
  items: HomeSpotCard[];
}

export interface Recommendations {
  ready: boolean;
  savedCount: number;
  minSaved: number;
  items: HomeSpotCard[];
}

export interface RegionLabel {
  sido: string | null;
  sigungu: string | null;
  dong: string | null;
  label: string;
}

export async function getNearby(coords: { lat: number; lng: number }): Promise<HomeCards> {
  return (await api.get("/home/nearby", { params: coords })) as unknown as HomeCards;
}

export async function getTrending(): Promise<HomeCards> {
  return (await api.get("/home/trending")) as unknown as HomeCards;
}

export async function getTastePicks(): Promise<HomeCards> {
  return (await api.get("/home/taste-picks")) as unknown as HomeCards;
}

export async function getRecommendations(coords?: {
  lat: number;
  lng: number;
}): Promise<Recommendations> {
  return (await api.get("/home/recommendations", {
    params: coords,
  })) as unknown as Recommendations;
}

export async function getRegionLabel(coords: {
  lat: number;
  lng: number;
}): Promise<RegionLabel | null> {
  return (await api.get("/map/region", { params: coords })) as unknown as RegionLabel | null;
}
