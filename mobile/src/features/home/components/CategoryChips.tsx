import { Pressable, ScrollView, StyleSheet, Text } from "react-native";
import type { RankCategory } from "@/features/home/api";
import { colors, spacing } from "@/constants/theme";

const OPTIONS: { key: RankCategory | null; label: string }[] = [
  { key: null, label: "전체" },
  { key: "SPOT", label: "관광지" },
  { key: "CAFE", label: "카페" },
  { key: "FOOD", label: "식당" },
];

interface Props {
  selected: RankCategory | null;
  onChange: (category: RankCategory | null) => void;
}

export function CategoryChips({ selected, onChange }: Props) {
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      style={styles.bar}
      contentContainerStyle={styles.row}
    >
      {OPTIONS.map((option) => {
        const active = option.key === selected;
        return (
          <Pressable
            key={option.label}
            testID={`rank-category-${option.key ?? "all"}`}
            accessibilityRole="tab"
            accessibilityState={{ selected: active }}
            onPress={() => onChange(option.key)}
            style={[styles.chip, active && styles.chipActive]}
          >
            <Text style={[styles.label, active && styles.labelActive]}>{option.label}</Text>
          </Pressable>
        );
      })}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  bar: { flexGrow: 0, marginTop: spacing.sm },
  row: { gap: 7, paddingHorizontal: spacing.lg },
  chip: {
    height: 32,
    paddingHorizontal: 14,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.fill,
    borderWidth: 1,
    borderColor: colors.line,
  },
  chipActive: { backgroundColor: colors.accent, borderColor: colors.accent },
  label: { fontSize: 12.5, fontWeight: "700", letterSpacing: -0.2, color: colors.sec },
  labelActive: { color: colors.onImage, fontWeight: "800" },
});
