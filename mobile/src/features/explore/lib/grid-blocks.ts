import type { OverseasPost } from "@/features/feed/posts-api";

export type GridBlock =
  | { type: "row3"; items: [OverseasPost, OverseasPost, OverseasPost] }
  | { type: "big"; big: OverseasPost; side: [OverseasPost, OverseasPost] };

export function toGridBlocks(items: OverseasPost[]): {
  blocks: GridBlock[];
  leftover: OverseasPost[];
} {
  const blocks: GridBlock[] = [];
  let i = 0;
  let block = 0;
  while (i + 3 <= items.length) {
    const a = items[i];
    const b = items[i + 1];
    const c = items[i + 2];
    if (block % 3 === 1) {
      blocks.push({ type: "big", big: a, side: [b, c] });
    } else {
      blocks.push({ type: "row3", items: [a, b, c] });
    }
    i += 3;
    block += 1;
  }
  return { blocks, leftover: items.slice(i) };
}
