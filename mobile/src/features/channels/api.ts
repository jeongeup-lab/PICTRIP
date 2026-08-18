import { api } from "@/lib/api-client";

export type ChannelKey = "spot" | "cafe" | "food" | "festa" | "hidden";

export type ChannelMeta = {
  key: ChannelKey;
  label: string;
  thumbnailUrl: string | null;
  available: boolean;
};

export type ChannelCard = {
  contentId: string | null;
  title: string;
  regionLabel: string;
  imageUrl: string | null;
  dist: number | null;
  rank: number | null;
  dday: string | null;
  line: string | null;
  tag: string | null;
  saveable: boolean;
};

export type ChannelCoords = { lat: number; lng: number };

function roundedParams(
  coords?: ChannelCoords,
): { lat: number; lng: number } | Record<string, never> {
  if (!coords) return {};
  return { lat: Math.round(coords.lat * 1000) / 1000, lng: Math.round(coords.lng * 1000) / 1000 };
}

export async function getChannels(coords?: ChannelCoords): Promise<{ channels: ChannelMeta[] }> {
  return (await api.get("/home/channels", { params: roundedParams(coords) })) as unknown as {
    channels: ChannelMeta[];
  };
}

export async function getChannelCards(
  key: ChannelKey,
  coords?: ChannelCoords,
): Promise<{ key: ChannelKey; label: string; cards: ChannelCard[] }> {
  return (await api.get(`/home/channels/${key}`, { params: roundedParams(coords) })) as unknown as {
    key: ChannelKey;
    label: string;
    cards: ChannelCard[];
  };
}
