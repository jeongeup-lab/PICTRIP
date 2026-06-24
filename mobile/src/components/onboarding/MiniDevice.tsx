import type { ReactNode } from "react";
import { View, StyleSheet } from "react-native";
import { colors, shadows } from "@/constants/theme";

// The mockup renders a 392x828 "design frame" scaled by 0.602 into a 236x498 card.
const FRAME_W = 392;
const FRAME_H = 828;
const SCALE = 0.602;
const DEVICE_W = 236;
const DEVICE_H = 498;

/**
 * 236x498 rounded device card that shows a scaled-down rendering of a real app
 * screen. The inner screen is laid out at full 392px width then transformed by
 * scale(0.602) from the top-left corner (matching the mockup's CSS).
 */
export function MiniDevice({ children }: { children: ReactNode }) {
  return (
    <View style={styles.device}>
      <View style={styles.scaled}>{children}</View>
    </View>
  );
}

const styles = StyleSheet.create({
  device: {
    width: DEVICE_W,
    height: DEVICE_H,
    borderRadius: 34,
    overflow: "hidden",
    backgroundColor: colors.bg,
    borderWidth: 1,
    borderColor: "rgba(16,14,18,0.06)",
    marginTop: 12,
    ...shadows.card,
  },
  scaled: {
    position: "absolute",
    top: 0,
    left: 0,
    width: FRAME_W,
    height: FRAME_H,
    transform: [{ scale: SCALE }],
    transformOrigin: "top left",
  },
});
