import { StyleSheet, Text, View } from "react-native";
import { Image } from "expo-image";
import { colors, spacing } from "@/constants/theme";

interface Props {
  question: string;
  photoUri: string | null;
}

export function UserBubble({ question, photoUri }: Props) {
  return (
    <View style={styles.row}>
      <View style={styles.bubble}>
        {photoUri ? (
          <Image source={{ uri: photoUri }} style={styles.thumb} contentFit="cover" />
        ) : null}
        {question ? <Text style={styles.text}>{question}</Text> : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", justifyContent: "flex-end", paddingHorizontal: spacing.md },
  bubble: {
    maxWidth: "82%",
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingHorizontal: 14,
    paddingVertical: 9,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.fillStrong,
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    borderBottomRightRadius: 4,
    borderBottomLeftRadius: 16,
  },
  text: {
    flexShrink: 1,
    fontSize: 13.5,
    fontWeight: "600",
    letterSpacing: -0.2,
    color: colors.ink,
  },
  thumb: { width: 40, height: 40, borderRadius: 10 },
});
