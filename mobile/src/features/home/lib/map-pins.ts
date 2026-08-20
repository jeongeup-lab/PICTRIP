import type { HomeSpotCard } from "@/features/home/api";
import type { LatLng } from "@/features/map/lib/geo";
import type { NearbySpot } from "@/lib/api-types";

export interface PlacedCard {
  card: HomeSpotCard;
  lat: number;
  lng: number;
}

const MIN_SPAN_DEG = 0.02;

export function placed(cards: HomeSpotCard[]): PlacedCard[] {
  return cards.flatMap((card) =>
    card.lat !== null && card.lng !== null ? [{ card, lat: card.lat, lng: card.lng }] : [],
  );
}

export function pinsFrom(cards: PlacedCard[]): NearbySpot[] {
  return cards.map(({ card, lat, lng }) => ({
    contentId: card.contentId,
    title: card.title,
    firstImageUrl: card.imageUrl,
    addr1: card.regionLabel,
    mapx: lng,
    mapy: lat,
    category: card.category,
    dist: card.dist,
    categoryGroup: null,
    regionName: null,
    sigunguName: null,
    overview: null,
  }));
}

export function center(cards: PlacedCard[]): LatLng | null {
  if (cards.length === 0) return null;
  return {
    lat: cards.reduce((sum, c) => sum + c.lat, 0) / cards.length,
    lng: cards.reduce((sum, c) => sum + c.lng, 0) / cards.length,
  };
}

export function bounds(cards: PlacedCard[]): { sw: LatLng; ne: LatLng } | null {
  if (cards.length === 0) return null;
  const lat = widen(cards.map((c) => c.lat));
  const lng = widen(cards.map((c) => c.lng));
  return { sw: { lat: lat.min, lng: lng.min }, ne: { lat: lat.max, lng: lng.max } };
}

export function countsOf(cards: HomeSpotCard[]): { cafe: number; food: number; spot: number } {
  let cafe = 0;
  let food = 0;
  for (const card of cards) {
    const kind = card.category ?? "";
    if (/카페|디저트|베이커리/.test(kind)) cafe += 1;
    else if (/식당|음식|한식|일식|중식|양식|분식|뷔페|구이|육류|해물|국수/.test(kind)) food += 1;
  }
  return { cafe, food, spot: cards.length - cafe - food };
}

function widen(values: number[]): { min: number; max: number } {
  const min = Math.min(...values);
  const max = Math.max(...values);
  if (max - min >= MIN_SPAN_DEG) return { min, max };
  const mid = (min + max) / 2;
  return { min: mid - MIN_SPAN_DEG / 2, max: mid + MIN_SPAN_DEG / 2 };
}
