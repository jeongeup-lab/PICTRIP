export const FIT_TOP_PAD = 96;
export const FIT_SIDE_PAD = 40;
export const FIT_BOTTOM_MARGIN = 24;

export const DOCK_FIELD_PX = 46;
export const DOCK_PAD_BOTTOM_PX = 12;
export const DOCK_CHIP_ROW_PX = 42;
export const DOCK_ATTACH_ROW_PX = 73;
export const DOCK_PRIMER_PX = 47;

export function dockBasePx({ primer, attached }: { primer: boolean; attached: boolean }): number {
  const row = attached ? DOCK_ATTACH_ROW_PX : DOCK_CHIP_ROW_PX;
  const prompt = primer && !attached ? DOCK_PRIMER_PX : 0;
  return DOCK_FIELD_PX + DOCK_PAD_BOTTOM_PX + row + prompt;
}

export function mapFitPadding({ safeTop, dockHeight }: { safeTop: number; dockHeight: number }): {
  top: number;
  right: number;
  bottom: number;
  left: number;
} {
  return {
    top: safeTop + FIT_TOP_PAD,
    right: FIT_SIDE_PAD,
    bottom: dockHeight + FIT_BOTTOM_MARGIN,
    left: FIT_SIDE_PAD,
  };
}
