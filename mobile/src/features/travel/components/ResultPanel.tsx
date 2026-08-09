import type { ReactNode } from "react";
import { View, StyleSheet, type LayoutChangeEvent } from "react-native";
import { colors, shadows, spacing } from "@/constants/theme";

const PANEL_RADIUS = 20;

interface Props {
  bottom: number;
  onHeight: (px: number) => void;
  children: ReactNode;
}

export function ResultPanel({ bottom, onHeight, children }: Props) {
  return (
    <View
      testID="travel-result-panel"
      style={[panelStyles.root, { bottom }]}
      pointerEvents="box-none"
      onLayout={(event: LayoutChangeEvent) => onHeight(event.nativeEvent.layout.height)}
    >
      <View testID="travel-result-surface" style={panelStyles.surface} pointerEvents="box-none">
        {children}
      </View>
    </View>
  );
}

export const panelStyles = StyleSheet.create({
  root: {
    position: "absolute",
    left: spacing.sm,
    right: spacing.sm,
    borderRadius: PANEL_RADIUS,
    backgroundColor: colors.inset,
    ...shadows.card,
  },
  surface: {
    paddingTop: 12,
    paddingBottom: 12,
    borderRadius: PANEL_RADIUS,
    borderWidth: 1,
    borderColor: colors.glassBorder,
    overflow: "hidden",
  },
});
