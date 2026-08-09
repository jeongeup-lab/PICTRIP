export const FIT_TOP_PAD = 96;
export const FIT_SIDE_PAD = 40;
export const FIT_BOTTOM_MARGIN = 24;

export const DOCK_FIELD_PX = 46;
export const DOCK_PAD_BOTTOM_PX = 12;
export const DOCK_CHIP_ROW_PX = 42;
export const DOCK_ATTACH_ROW_PX = 73;
export const DOCK_PRIMER_PX = 47;

export const PANEL_PAD_PX = 26;
export const PANEL_HEAD_PX = 22;
export const PANEL_COPY_PX = 48;
export const PANEL_CHIP_ROW_PX = 33;
export const PANEL_CHIP_GAP_PX = 12;

export function dockBasePx({
  primer,
  attached,
  chips,
}: {
  primer: boolean;
  attached: boolean;
  chips: boolean;
}): number {
  const row = attached ? DOCK_ATTACH_ROW_PX : chips ? DOCK_CHIP_ROW_PX : 0;
  const prompt = primer && !attached ? DOCK_PRIMER_PX : 0;
  return DOCK_FIELD_PX + DOCK_PAD_BOTTOM_PX + row + prompt;
}

export function panelBasePx({ chips, carousel }: { chips: boolean; carousel: boolean }): number {
  const chipBlock = chips ? PANEL_CHIP_ROW_PX + (carousel ? 0 : PANEL_CHIP_GAP_PX) : 0;
  return PANEL_PAD_PX + PANEL_HEAD_PX + PANEL_COPY_PX + chipBlock;
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
