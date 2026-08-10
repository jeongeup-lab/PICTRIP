import { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { colors, spacing } from "@/constants/theme";

export const WELCOME_TEXT = "안녕하세요, PICTRIP 어시스턴트예요.\n뭐든 물어보세요.";

const TYPE_INTERVAL_MS = 28;

export function WelcomeBubble() {
  const [shown, setShown] = useState(0);

  useEffect(() => {
    if (shown >= WELCOME_TEXT.length) return;
    const timer = setInterval(
      () => setShown((count) => Math.min(count + 1, WELCOME_TEXT.length)),
      TYPE_INTERVAL_MS,
    );
    return () => clearInterval(timer);
  }, [shown]);

  return (
    <View style={styles.row}>
      <View style={styles.bubble}>
        <Text style={styles.text}>{WELCOME_TEXT.slice(0, shown)}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", justifyContent: "flex-start", paddingHorizontal: spacing.md },
  bubble: {
    maxWidth: "82%",
    minHeight: 58,
    minWidth: 120,
    justifyContent: "center",
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.fill,
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    borderBottomRightRadius: 16,
    borderBottomLeftRadius: 4,
  },
  text: {
    fontSize: 13.5,
    fontWeight: "600",
    lineHeight: 20,
    letterSpacing: -0.2,
    color: colors.ink,
  },
});
