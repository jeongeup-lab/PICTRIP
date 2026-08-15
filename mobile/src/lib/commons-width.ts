import { PixelRatio } from "react-native";

export const COMMONS_WIDTHS = [250, 330, 500, 960, 1280] as const;

export const commonsWidthFor = (dp: number): number => {
  const physical = dp * PixelRatio.get();
  return COMMONS_WIDTHS.find((w) => w >= physical) ?? COMMONS_WIDTHS[COMMONS_WIDTHS.length - 1];
};
