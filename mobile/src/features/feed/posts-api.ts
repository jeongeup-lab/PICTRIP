import { api } from "@/lib/api-client";

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
};

export type MatchCard = {
  contentId: string;
  title: string;
  regionLabel: string;
  imageUrl: string;
  overviewFirst: string | null;
};

export type PostsPage = {
  seed: string;
  items: OverseasPost[];
  nextCursor: string | null;
  hasMore: boolean;
};

export type MatchesResult = {
  overseasId: number;
  matches: MatchCard[];
};

export async function getPosts(params: {
  seed?: string;
  cursor?: string;
  limit?: number;
}): Promise<PostsPage> {
  return (await api.get("/feed", { params })) as unknown as PostsPage;
}

export async function getMatches(id: number): Promise<MatchesResult> {
  return (await api.get(`/overseas/${id}/matches`)) as unknown as MatchesResult;
}
