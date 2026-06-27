/**
 * Mirrors backend JSend envelope + module schemas. Keep field names in sync
 * (camelCase). Source: backend/app/modules/<code>/schemas.py
 */

export interface ResponseMeta {
  traceId: string;
  requestedAt?: string;
  pagination?: {
    nextCursor: string | null;
    hasMore: boolean;
    count: number;
  };
}

export interface ErrorPayload {
  code: string;
  message: string;
  details?: { field: string; issue: string }[];
  traceId?: string;
}

export interface Envelope<T> {
  data: T | null;
  error: ErrorPayload | null;
  meta: ResponseMeta;
}

// Canonical card — extended across endpoints.
export interface SpotCard {
  contentId: string;
  title: string;
  firstImageUrl: string | null;
  addr1?: string | null;
  mapx?: number | null;
  mapy?: number | null;
  category: string | null;
}

export interface PhotoMatch extends SpotCard {
  similarity: number; // 0..1 (1 - cosine distance)
  distance?: number | null; // metres; present only when query carried lat/lng
  regionName?: string | null;
  sigunguName?: string | null;
}

export interface PhotoSearchResult {
  matches: PhotoMatch[];
  queryHadLocation: boolean;
}

export interface HeroTile {
  id: number;
  slug: string;
  title: string; // keeps \n — render multi-line
  subtitle: string | null;
  coverUrl: string | null;
}

export interface MoodRailDto {
  id: number;
  title: string;
  subtitle: string | null;
  spots: SpotCard[];
}

export interface HomeFeed {
  heroes: HeroTile[];
  rails: MoodRailDto[];
}

export interface CurationDetail {
  id: number;
  type: string;
  slug: string;
  title: string;
  lead: string | null;
  intro: string | null;
  coverUrl: string | null;
  spots: SpotCard[];
}

export interface SpotImage {
  originImageUrl: string;
  smallImageUrl: string | null;
}

export interface SpotIntro {
  usetime: string | null;
  restdate: string | null;
  parking: string | null;
  infocenter: string | null;
  firstmenu: string | null;
  treatmenu: string | null;
}

export interface SpotDetail {
  contentId: string;
  title: string;
  firstImageUrl: string | null;
  addr1: string | null;
  addr2: string | null;
  mapx: number | null;
  mapy: number | null;
  overview: string | null;
  homepage: string | null;
  tel: string | null;
  category: string | null;
  regionName: string | null;
  sigunguName: string | null;
  detailStatus: string;
  images: SpotImage[];
  intro: SpotIntro | null;
}

export interface NearbySpot extends SpotCard {
  dist: number | null;
  categoryGroup: string | null; // attraction/food/cafe/leisure/shopping — drives marker glyph
  regionName: string | null;
  sigunguName: string | null;
  overview: string | null;
}

export interface RegionLabel {
  sido: string | null;
  sigungu: string | null;
  dong: string | null;
  label: string;
}

export interface Centroid {
  lat: number;
  lng: number;
}

export interface SigunguNode {
  sigunguCode: string;
  sigunguName: string;
  centroid: Centroid;
}

export interface RegionNode {
  regionCode: string;
  regionName: string;
  centroid: Centroid;
  sigungus: SigunguNode[];
}

export interface User {
  id: number;
  displayName: string | null;
  email: string | null;
  avatarUrl: string | null;
  isOnboarded: boolean;
  createdAt: string | null;
}

export interface TokenPair {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
  user: User;
}
