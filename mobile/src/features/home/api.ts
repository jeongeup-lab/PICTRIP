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
  baseDate?: string | null;
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

export type RankCategory = "SPOT" | "CAFE" | "FOOD";

export async function getNearby(
  coords: { lat: number; lng: number },
  category?: RankCategory,
): Promise<HomeCards> {
  return (await api.get("/home/nearby", {
    params: { ...coords, ...(category ? { category } : {}) },
  })) as unknown as HomeCards;
}

export async function getTrending(category?: RankCategory): Promise<HomeCards> {
  return (await api.get("/home/trending", {
    params: category ? { category } : {},
  })) as unknown as HomeCards;
}

export type TasteCategory = "SPOT" | "CAFE" | "FOOD" | "FESTA" | "HIDDEN";

export async function getTastePicks(limit: number, category?: TasteCategory): Promise<HomeCards> {
  return (await api.get("/home/taste-picks", {
    params: { limit, ...(category ? { category } : {}) },
  })) as unknown as HomeCards;
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
