import { View, Text, StyleSheet } from "react-native";
import type { Congestion } from "@/lib/api-types";
import { colors } from "@/constants/theme";

const LABELS: Record<"low" | "medium" | "high", string> = {
  low: "여유",
  medium: "보통",
  high: "혼잡",
};

export function CongestionChip({ level }: { level: Congestion }) {
  if (!level) return null;
  return (
    <View style={styles.chip}>
      <Text style={styles.text}>{LABELS[level]}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  chip: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 999,
    backgroundColor: colors.fill,
    alignSelf: "flex-start",
  },
  text: { fontSize: 11, fontWeight: "700", color: colors.sec },
});
