import type { PhotoMatch } from "@/lib/api-types";

export type SortMode = "similarity" | "distance";

/** Client-side re-sort of server matches (no refetch). distance asc with a
 * similarity-desc tiebreak; matches without distance sink to the bottom. */
export function sortMatches(matches: PhotoMatch[], mode: SortMode): PhotoMatch[] {
  const copy = [...matches];
  if (mode === "distance") {
    copy.sort((a, b) => {
      const ad = a.distance ?? Infinity;
      const bd = b.distance ?? Infinity;
      if (ad !== bd) return ad - bd;
      return b.similarity - a.similarity;
    });
  } else {
    copy.sort((a, b) => b.similarity - a.similarity);
  }
  return copy;
}
