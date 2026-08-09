import { idleChips, type Chip } from "@/features/travel/lib/chips";

export type DockChip = { kind: "photo" } | { kind: "query"; chip: Chip };

function queries(chips: Chip[]): DockChip[] {
  return chips.map((chip) => ({ kind: "query", chip }));
}

export function dockChips(): DockChip[] {
  return [{ kind: "photo" }, ...queries(idleChips())];
}
