import { ScrollView, Pressable, Text, StyleSheet } from "react-native";
import type { NearChip } from "@/features/travel/lib/starter-chips";
import { colors, radii, spacing } from "@/constants/theme";

interface Props {
  chips: NearChip[];
  disabled?: boolean;
  onChipPress: (chip: NearChip) => void;
}

export function StarterChipRow({ chips, disabled, onChipPress }: Props) {
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      keyboardShouldPersistTaps="handled"
      contentContainerStyle={styles.row}
    >
      {chips.map((chip, index) => (
        <Pressable
          key={chip.label}
          testID={`travel-starter-${index}`}
          accessibilityRole="button"
          accessibilityLabel={chip.label}
          disabled={disabled}
          onPress={() => onChipPress(chip)}
          style={({ pressed }) => [styles.chip, (pressed || disabled) && styles.pressed]}
        >
          <Text style={styles.label}>{chip.label}</Text>
        </Pressable>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  row: { paddingHorizontal: spacing.md, gap: 7, alignItems: "center" },
  chip: {
    height: 34,
    paddingHorizontal: 14,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.glassBorder,
    backgroundColor: colors.inset,
    alignItems: "center",
    justifyContent: "center",
  },
  label: { fontSize: 13, fontWeight: "600", letterSpacing: -0.2, color: colors.ink },
  pressed: { opacity: 0.7 },
});
