import { api } from "@/lib/api-client";

export type MatchCard = {
  contentId: string;
  title: string;
  regionLabel: string;
  imageUrl: string;
  overviewFirst: string | null;
};

export type OverseasPost = {
  id: number;
  nameKo: string;
  countryCode: string;
  countryNameKo: string;
  descriptionKo: string | null;
  imageUrl: string;
  imageAuthor: string | null;
  imageLicense: string | null;
  imageLicenseUrl: string | null;
  imageSourceUrl: string;
  matches: MatchCard[];
};

export type PostsPage = {
  seed: string;
  items: OverseasPost[];
  nextCursor: string | null;
  hasMore: boolean;
};

export async function getExplore(params: {
  seed?: string;
  cursor?: string;
  limit?: number;
}): Promise<PostsPage> {
  return (await api.get("/explore", { params })) as unknown as PostsPage;
}
