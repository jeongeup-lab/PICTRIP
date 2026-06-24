import { View, Text, Image, StyleSheet } from "react-native";
import { colors, shadows } from "@/constants/theme";

/** STEP 2 preview: "분석중" screen (.scr-an). Rendered inside the 392px design frame. */
export function MiniAnalyzeScreen() {
  return (
    <View style={styles.root}>
      <View style={styles.thumb}>
        <Image
          source={{ uri: "https://picsum.photos/seed/select/200/200" }}
          style={styles.thumbImg}
        />
      </View>
      <Text style={styles.title}>사진을 분석하고 있어요</Text>
      <Text style={styles.sub}>잠시만 기다려 주세요</Text>
      <View style={styles.bar}>
        <View style={styles.barFill} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: colors.bg,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 44,
  },
  thumb: {
    width: 92,
    height: 92,
    borderRadius: 20,
    overflow: "hidden",
    marginBottom: 26,
    ...shadows.card,
  },
  thumbImg: { width: "100%", height: "100%" },
  title: {
    fontSize: 20,
    fontWeight: "700",
    letterSpacing: -0.36,
    marginBottom: 6,
    color: colors.ink,
  },
  sub: { fontSize: 13, color: colors.sec, marginBottom: 30 },
  bar: {
    width: "100%",
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.skeleton,
    overflow: "hidden",
  },
  barFill: {
    position: "absolute",
    left: "18%",
    width: "42%",
    height: "100%",
    borderRadius: 2,
    backgroundColor: colors.ink,
  },
});
