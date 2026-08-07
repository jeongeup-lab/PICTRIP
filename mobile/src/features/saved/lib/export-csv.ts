import type { SpotCard } from "@/lib/api-types";

const HEADER = ["contentId", "title", "address", "category", "lat", "lng"];

function cell(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return "";
  const text = String(value);
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

export function buildSavedCsv(list: readonly SpotCard[]): string {
  const rows = list.map((spot) =>
    [spot.contentId, spot.title, spot.addr1, spot.category, spot.mapy, spot.mapx]
      .map(cell)
      .join(","),
  );
  return [HEADER.join(","), ...rows].join("\n");
}
