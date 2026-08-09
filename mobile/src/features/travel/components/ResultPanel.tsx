import type { ReactNode } from "react";
import { View, StyleSheet } from "react-native";
import { colors, shadows, spacing } from "@/constants/theme";

export function ResultPanel({ bottom, children }: { bottom: number; children: ReactNode }) {
  return (
    <View
      testID="travel-result-panel"
      style={[panelStyles.root, { bottom }]}
      pointerEvents="box-none"
    >
      {children}
    </View>
  );
}

export const panelStyles = StyleSheet.create({
  root: {
    position: "absolute",
    left: spacing.sm,
    right: spacing.sm,
    paddingTop: 12,
    paddingBottom: 12,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: colors.glassBorder,
    backgroundColor: colors.inset,
    overflow: "hidden",
    ...shadows.card,
  },
});
