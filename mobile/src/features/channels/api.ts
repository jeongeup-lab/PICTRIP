import { api } from "@/lib/api-client";

export type ChannelKey = "around" | "hot" | "hidden" | "festa" | "pets" | "snap";

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

export async function getChannels(): Promise<{ channels: ChannelMeta[] }> {
  return (await api.get("/home/channels")) as unknown as { channels: ChannelMeta[] };
}

export async function getChannelCards(
  key: ChannelKey,
  coords?: { lat: number; lng: number },
): Promise<{ key: ChannelKey; label: string; cards: ChannelCard[] }> {
  return (await api.get(`/home/channels/${key}`, {
    params: coords ? { lat: coords.lat, lng: coords.lng } : undefined,
  })) as unknown as { key: ChannelKey; label: string; cards: ChannelCard[] };
}
