import { api } from "@/lib/api-client";
import type { PostsPage } from "@/features/feed/posts-api";

export async function getExplore(params: {
  seed?: string;
  cursor?: string;
  limit?: number;
}): Promise<PostsPage> {
  return (await api.get("/explore", { params })) as unknown as PostsPage;
}
