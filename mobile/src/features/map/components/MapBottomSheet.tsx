import { type ReactNode } from "react";
import type { Animated } from "react-native";
import { GlassSheet, SCREEN_H } from "@/components/GlassSheet";
import { sheetSnapY, type SheetSnap } from "@/features/map/lib/sheet-snap";

type Snap = SheetSnap;

interface Props {
  snap: Snap;
  onSnapChange: (s: Snap) => void;
  headerExtra?: ReactNode;
  children: ReactNode;
  onTranslate?: (v: Animated.Value) => void;
  snapY?: Record<Snap, number>;
}

export const H = SCREEN_H;

export const SHEET_SNAP_Y: Record<Snap, number> = sheetSnapY(H);

export function MapBottomSheet({
  snap,
  onSnapChange,
  headerExtra,
  children,
  onTranslate,
  snapY = SHEET_SNAP_Y,
}: Props) {
  return (
    <GlassSheet
      snap={snap}
      snapY={snapY}
      onSnapChange={onSnapChange}
      headerExtra={headerExtra}
      onTranslate={onTranslate}
    >
      {children}
    </GlassSheet>
  );
}
