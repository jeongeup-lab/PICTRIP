import type { ReactNode } from "react";
import { View, Text, StyleSheet } from "react-native";
import { colors, radii, spacing } from "@/constants/theme";

interface Props {
  title: string;
  text?: string;
  tone?: "default" | "danger";
  children?: ReactNode;
  testID?: string;
}

export function InfoBox({ title, text, tone = "default", children, testID }: Props) {
  const danger = tone === "danger";
  return (
    <View style={[styles.box, danger && styles.boxDanger]} testID={testID}>
      <Text style={[styles.title, danger && styles.titleDanger]}>{title}</Text>
      {text ? <Text style={styles.text}>{text}</Text> : null}
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  box: {
    marginHorizontal: spacing.md,
    marginTop: spacing.md,
    padding: spacing.md,
    borderRadius: radii.lg + 4,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.raise,
  },
  boxDanger: { borderColor: colors.accentFill, backgroundColor: colors.accentFill },
  title: { fontSize: 13.5, fontWeight: "800", letterSpacing: -0.2, color: colors.ink },
  titleDanger: { color: colors.accentText },
  text: { marginTop: 7, fontSize: 12.5, lineHeight: 19, color: colors.sec },
});
