import { api } from "@/lib/api-client";
import type { HomeFeed } from "@/lib/api-types";

export async function getHomeFeed(): Promise<HomeFeed> {
  return (await api.get("/home/feed")) as unknown as HomeFeed;
}
