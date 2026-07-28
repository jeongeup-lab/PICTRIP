import type { TravelSpot } from "@/features/travel/api";

export const BOARD_CAP = 12;

export function mergeBoardSpots(lists: TravelSpot[][], cap = BOARD_CAP): TravelSpot[] {
  const seen = new Set<string>();
  const merged: TravelSpot[] = [];
  const longest = Math.max(0, ...lists.map((list) => list.length));
  for (let i = 0; i < longest; i += 1) {
    for (const list of lists) {
      const spot = list[i];
      if (!spot || seen.has(spot.contentId)) continue;
      seen.add(spot.contentId);
      merged.push(spot);
      if (merged.length >= cap) return merged;
    }
  }
  return merged;
}

export function boardPinHeight(index: number): number {
  return index % 3 === 1 ? 224 : 178;
}

export function splitBoardColumns<T>(cells: T[]): [T[], T[]] {
  const left: T[] = [];
  const right: T[] = [];
  cells.forEach((cell, index) => (index % 2 === 0 ? left : right).push(cell));
  return [left, right];
}
