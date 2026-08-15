import { api } from "@/lib/api-client";
import type { SpotCard } from "@/lib/api-types";

export const SAVED_PAGE_LIMIT = 60;

export async function listSaved(): Promise<SpotCard[]> {
  return (await api.get("/users/me/saved", {
    params: { limit: SAVED_PAGE_LIMIT },
  })) as unknown as SpotCard[];
}

export async function saveSpot(contentId: string): Promise<void> {
  await api.post(`/users/me/saved/${contentId}`);
}

export async function unsaveSpot(contentId: string): Promise<void> {
  await api.delete(`/users/me/saved/${contentId}`);
}
