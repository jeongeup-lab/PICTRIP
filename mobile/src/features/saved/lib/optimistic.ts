import type { SpotCard } from "@/lib/api-types";

export function removeById(list: SpotCard[], contentId: string): SpotCard[] {
  return list.filter((c) => c.contentId !== contentId);
}

export function containsId(list: SpotCard[] | undefined, contentId: string): boolean {
  return !!list?.some((c) => c.contentId === contentId);
}
