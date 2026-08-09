import type { ReactNode } from "react";
import { View, StyleSheet } from "react-native";
import { colors, shadows, spacing } from "@/constants/theme";

const PANEL_RADIUS = 20;

export function ResultPanel({ bottom, children }: { bottom: number; children: ReactNode }) {
  return (
    <View
      testID="travel-result-panel"
      style={[panelStyles.root, { bottom }]}
      pointerEvents="box-none"
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
