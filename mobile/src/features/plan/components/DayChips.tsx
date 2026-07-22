import { Pressable, ScrollView, Text, StyleSheet } from "react-native";
import { colors, spacing } from "@/constants/theme";

interface Props {
  days: number[];
  value: number | null;
  onChange: (day: number | null) => void;
}

function Chip({
  label,
  selected,
  onPress,
}: {
  label: string;
  selected: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable style={[styles.chip, selected && styles.chipOn]} onPress={onPress}>
      <Text style={[styles.text, selected && styles.textOn]}>{label}</Text>
    </Pressable>
  );
}

export function DayChips({ days, value, onChange }: Props) {
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.row}
    >
      <Chip label="전체" selected={value === null} onPress={() => onChange(null)} />
      {days.map((day) => (
        <Chip
          key={day}
          label={`Day ${day}`}
          selected={value === day}
          onPress={() => onChange(day)}
        />
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  row: { gap: 8, paddingHorizontal: spacing.lg, paddingVertical: 12 },
  chip: {
    height: 34,
    paddingHorizontal: 16,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.bg,
    alignItems: "center",
    justifyContent: "center",
  },
  chipOn: { backgroundColor: colors.ink, borderColor: colors.ink },
  text: { fontSize: 13.5, fontWeight: "700", color: colors.sec },
  textOn: { color: colors.onImage },
});
