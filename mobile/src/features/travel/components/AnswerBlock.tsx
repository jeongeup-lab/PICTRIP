import { View, Text, StyleSheet } from "react-native";
import type { AnswerPart } from "@/features/travel/api";
import { colors } from "@/constants/theme";

interface Props {
  answer: AnswerPart[];
}

export function AnswerBlock({ answer }: Props) {
  return (
    <View style={styles.root}>
      <Text style={styles.say}>
        {answer.map((part, index) => (
          <Text key={`${index}-${part.text}`} style={part.emphasis ? styles.emphasis : undefined}>
            {part.text}
          </Text>
        ))}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { marginTop: 14, paddingHorizontal: 4 },
  say: { fontSize: 14.5, lineHeight: 22.5, letterSpacing: -0.2, color: colors.ink },
  emphasis: { color: colors.accentText, fontWeight: "800" },
});
