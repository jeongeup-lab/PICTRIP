import type { ResolvedPlace } from "@/features/plan/api";

export type SplitPlaces = { usable: number[]; missing: number[] };

export function splitPlaces(places: ResolvedPlace[]): SplitPlaces {
  const usable: number[] = [];
  const missing: number[] = [];
  places.forEach((place, index) => {
    if (place.extracted.placeType === "region") return;
    if (place.status === "unmatched") missing.push(index);
    else usable.push(index);
  });
  return { usable, missing };
}

export function defaultSelection(places: ResolvedPlace[]): number[] {
  return splitPlaces(places).usable;
}

export function toggleIndex(selected: number[], index: number): number[] {
  return selected.includes(index)
    ? selected.filter((i) => i !== index)
    : [...selected, index].sort((a, b) => a - b);
}

export function requestedDays(tripDays: number | null): number | null {
  return tripDays != null && tripDays >= 1 && tripDays <= 7 ? tripDays : null;
}
