import { View, Text, StyleSheet } from "react-native";
import { colors, radii } from "@/constants/theme";

export function MiniDevice() {
  return (
    <View style={styles.device}>
      <View style={styles.barSm} />
      <View style={styles.barLg} />
      <View style={styles.photo} />
      <View style={styles.cta}>
        <Text style={styles.ctaLabel}>분석하기</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  device: {
    width: 196,
    height: 356,
    borderRadius: 22,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.bg,
    marginTop: 16,
    paddingVertical: 16,
    paddingHorizontal: 14,
    gap: 10,
    overflow: "hidden",
    shadowColor: "#171719",
    shadowOpacity: 0.08,
    shadowRadius: 24,
    shadowOffset: { width: 0, height: 10 },
    elevation: 4,
  },
  barSm: { width: 74, height: 9, borderRadius: 5, backgroundColor: colors.skeleton },
  barLg: { width: 112, height: 9, borderRadius: 5, backgroundColor: colors.skeleton },
  photo: { flex: 1, borderRadius: radii.lg, overflow: "hidden", backgroundColor: colors.skeleton },
  cta: {
    height: 34,
    borderRadius: radii.md,
    backgroundColor: colors.accent,
    alignItems: "center",
    justifyContent: "center",
  },
  ctaLabel: { color: colors.onImage, fontSize: 11, fontWeight: "700" },
});
