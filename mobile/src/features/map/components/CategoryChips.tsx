import { ScrollView, Pressable, Text, StyleSheet } from "react-native";
import { CATEGORY_CHIPS, type NearbyCategory } from "@/features/map/lib/nearby-categories";
import { colors, spacing, radii } from "@/constants/theme";

interface Props {
  value: NearbyCategory | null;
  onChange: (v: NearbyCategory | null) => void;
}

export function CategoryChips({ value, onChange }: Props) {
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.row}
    >
      {CATEGORY_CHIPS.map((chip) => {
        const active = chip.value === value;
        return (
          <Pressable
            key={chip.label}
            onPress={() => onChange(chip.value)}
            style={[styles.chip, active && styles.chipActive]}
          >
            <Text style={[styles.label, active && styles.labelActive]}>{chip.label}</Text>
          </Pressable>
        );
      })}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  row: { gap: 8, paddingHorizontal: spacing.lg, paddingVertical: spacing.xs },
  chip: {
    height: 34,
    paddingHorizontal: 16,
    borderRadius: radii.pill,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.fill,
  },
  chipActive: { backgroundColor: colors.ink },
  label: { fontSize: 13.5, fontWeight: "700", color: colors.sec },
  labelActive: { color: colors.onImage },
});
