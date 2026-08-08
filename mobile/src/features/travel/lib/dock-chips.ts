import type { TravelSpot } from "@/features/travel/api";
import {
  anchorChips,
  idleChips,
  refineChips,
  type Chip,
  type ChipAnswer,
} from "@/features/travel/lib/chips";

export type DockChip =
  | { kind: "photo" }
  | { kind: "context"; title: string; expanded: boolean }
  | { kind: "query"; chip: Chip };

export interface DockChipsInput {
  answer: ChipAnswer | null;
  focused: TravelSpot | null;
  expanded: boolean;
  hasCoords: boolean;
  hasCrowd: boolean;
}

function queries(chips: Chip[]): DockChip[] {
  return chips.map((chip) => ({ kind: "query", chip }));
}

export function dockChips({
  answer,
  focused,
  expanded,
  hasCoords,
  hasCrowd,
}: DockChipsInput): DockChip[] {
  if (focused && expanded) {
    return [
      { kind: "context", title: focused.title, expanded: true },
      ...queries(anchorChips(hasCrowd)),
    ];
  }

  const refine = refineChips(answer?.refinements);
  const trailing = refine.length > 0 ? refine : answer ? [] : idleChips(hasCoords);
  const context: DockChip[] = focused
    ? [{ kind: "context", title: focused.title, expanded: false }]
    : [];

  return [{ kind: "photo" }, ...context, ...queries(trailing)];
}
