import { Pressable, View, Text, StyleSheet } from "react-native";
import type { AnswerPart } from "@/features/travel/api";
import type { Chip } from "@/features/travel/lib/chips";
import { colors } from "@/constants/theme";

interface Props {
  answer: AnswerPart[];
  chips: Chip[];
  onSuggest: (chip: Chip) => void;
}

export function AnswerBlock({ answer, chips, onSuggest }: Props) {
  return (
    <View style={styles.root}>
      <Text style={styles.say}>
        {answer.map((part, index) => (
          <Text key={`${index}-${part.text}`} style={part.emphasis ? styles.emphasis : undefined}>
            {part.text}
          </Text>
        ))}
      </Text>

      {chips.length > 0 ? (
        <View style={styles.chips}>
          {chips.map((chip) => (
            <Pressable
              key={chip.label}
              testID={`answer-suggestion-${chip.label}`}
              style={({ pressed }) => [styles.chip, pressed && styles.chipPressed]}
              onPress={() => onSuggest(chip)}
            >
              <Text style={styles.chipText}>{chip.label}</Text>
            </Pressable>
          ))}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { marginTop: 14, paddingTop: 14, borderTopWidth: 1, borderTopColor: colors.line },
  say: { fontSize: 14.5, lineHeight: 22.5, letterSpacing: -0.2, color: colors.ink },
  emphasis: { color: colors.accentText, fontWeight: "800" },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 7, marginTop: 16 },
  chip: {
    height: 34,
    paddingHorizontal: 14,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: colors.line,
    justifyContent: "center",
    backgroundColor: colors.bg,
  },
  chipPressed: { backgroundColor: colors.fill },
  chipText: { fontSize: 13, fontWeight: "700", color: colors.sec },
});
