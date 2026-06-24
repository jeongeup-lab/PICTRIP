import { View, Text, StyleSheet } from "react-native";
import Svg, { Rect } from "react-native-svg";
import { colors } from "@/constants/theme";

interface MiniStatusBarProps {
  /** When true, render white (for use over a dark hero). */
  onImage?: boolean;
  /** Absolutely position at the top (over hero). */
  overlay?: boolean;
}

/** Scaled-down iOS-style status bar used inside the mini-device previews (392px frame). */
export function MiniStatusBar({ onImage = false, overlay = false }: MiniStatusBarProps) {
  const tint = onImage ? colors.onImage : colors.ink;
  return (
    <View style={[styles.bar, overlay && styles.overlay]}>
      <Text style={[styles.time, { color: tint }]}>9:41</Text>
      <Svg width={18} height={12} viewBox="0 0 18 12">
        <Rect x={0} y={3} width={2.5} height={6} rx={1} fill={tint} />
        <Rect x={4} y={1.5} width={2.5} height={7.5} rx={1} fill={tint} />
        <Rect x={8} y={0} width={2.5} height={9} rx={1} fill={tint} />
      </Svg>
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    height: 44,
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-between",
    paddingHorizontal: 26,
    paddingBottom: 6,
  },
  overlay: { position: "absolute", top: 0, left: 0, right: 0, zIndex: 2 },
  time: { fontSize: 15, fontWeight: "600" },
});
