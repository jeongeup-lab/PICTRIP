import type { TravelSpot } from "@/features/travel/api";
import {
  contextChips,
  idleChips,
  refineChips,
  type Chip,
  type ChipAnswer,
} from "@/features/travel/lib/chips";

export type DockChip = { kind: "photo" } | { kind: "query"; chip: Chip };

export interface PanelChipsInput {
  answer: ChipAnswer | null;
  focused: TravelSpot | null;
  hasCrowd: boolean;
}

function queries(chips: Chip[]): DockChip[] {
  return chips.map((chip) => ({ kind: "query", chip }));
}

export function dockChips(): DockChip[] {
  return [{ kind: "photo" }, ...queries(idleChips())];
}

export function panelChips({ answer, focused, hasCrowd }: PanelChipsInput): DockChip[] {
  const context = focused ? contextChips(focused.title, hasCrowd) : [];
  return [{ kind: "photo" }, ...queries([...context, ...refineChips(answer?.refinements)])];
}
