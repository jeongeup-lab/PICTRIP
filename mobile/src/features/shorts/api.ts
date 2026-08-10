import { api } from "@/lib/api-client";

export type ShortsSpot = {
  contentId: string;
  title: string;
  regionLabel: string;
  imageUrl: string | null;
};

export type ShortsCardData = {
  videoId: string;
  title: string;
  channelTitle: string;
  thumbnailUrl: string;
  viewCount: number;
  anchorLabel: string;
  spots: ShortsSpot[];
};

export type ShortsPage = {
  items: ShortsCardData[];
  nextCursor: string | null;
  hasMore: boolean;
};

export async function getShorts(params: { cursor?: string; limit?: number }): Promise<ShortsPage> {
  return (await api.get("/shorts", { params })) as unknown as ShortsPage;
}
