import { View, Text, StyleSheet, StatusBar } from "react-native";
import Svg, { Path, Circle, Rect } from "react-native-svg";

/**
 * Full-screen splash matching docs/mockups/01-splash.html.
 * Pure black background with a line-drawn selfie figure + PicTrip wordmark.
 * Intentionally monochrome black/white (not the app's light theme).
 */
export function SplashScreen() {
  return (
    <View style={styles.root}>
      <StatusBar barStyle="light-content" />
      <View style={styles.center}>
        <Svg width={92} height={92} viewBox="0 0 48 48" fill="none">
          {/* head */}
          <Circle cx={20} cy={10} r={3.6} {...stroke} />
          {/* body */}
          <Path d="M20 13.6 V28.5" {...stroke} />
          {/* legs */}
          <Path d="M20 28.5 L15 40" {...stroke} />
          <Path d="M20 28.5 L25 40" {...stroke} />
          {/* arms */}
          <Path d="M20 18 L26.5 15" {...stroke} />
          <Path d="M20 18.5 L15.5 24" {...stroke} />
          {/* phone (solid white) */}
          <Rect x={26} y={11.4} width={8} height={5.2} rx={1.6} fill="#fff" />
          {/* lens */}
          <Circle cx={30} cy={14} r={1.3} fill="#000" />
        </Svg>
        <Text style={styles.logo}>PicTrip</Text>
      </View>
    </View>
  );
}

const stroke = {
  stroke: "#fff",
  fill: "none",
  strokeWidth: 2.4,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#000" },
  center: { flex: 1, alignItems: "center", justifyContent: "center", gap: 24 },
  logo: { color: "#fff", fontWeight: "800", fontSize: 38, letterSpacing: -1 },
});
