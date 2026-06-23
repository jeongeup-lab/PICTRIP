import { api } from "@/lib/api-client";
import type { SpotCard } from "@/lib/api-types";

/** Saved spots — single page (limit 60). Pagination meta is dropped by the
 * api-client unwrap; infinite scroll is out of scope for P3 (spec §5). */
export async function listSaved(): Promise<SpotCard[]> {
  return (await api.get("/users/me/saved", { params: { limit: 60 } })) as unknown as SpotCard[];
}

/** Idempotent save (backend returns 201 new / 200 duplicate). */
export async function saveSpot(contentId: string): Promise<void> {
  await api.post(`/users/me/saved/${contentId}`);
}

/** Idempotent unsave (204). */
export async function unsaveSpot(contentId: string): Promise<void> {
  await api.delete(`/users/me/saved/${contentId}`);
}
