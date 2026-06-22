import { api } from "@/lib/api-client";
import type { CurationDetail } from "@/lib/api-types";

export async function getCuration(slug: string): Promise<CurationDetail> {
  return (await api.get(`/curations/${slug}`)) as unknown as CurationDetail;
}
