import { useEffect, useState } from "react";
import { ActivityIndicator, View, Text, StyleSheet } from "react-native";
import { colors, spacing } from "@/constants/theme";

const SLOW_AFTER_MS = 6000;

interface Props {
  title: string;
  sub?: string;
  slowSub?: string;
}

export function PlanLoading({ title, sub, slowSub }: Props) {
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    if (!slowSub) return;
    const timer = setTimeout(() => setSlow(true), SLOW_AFTER_MS);
    return () => clearTimeout(timer);
  }, [slowSub]);

  const caption = slow && slowSub ? slowSub : sub;

  return (
    <View style={styles.root}>
      <ActivityIndicator size="small" color={colors.ink} />
      <Text style={styles.title}>{title}</Text>
      {caption ? <Text style={styles.sub}>{caption}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { paddingTop: 130, paddingHorizontal: spacing.lg, alignItems: "center" },
  title: {
    marginTop: 18,
    fontSize: 15.5,
    fontWeight: "600",
    letterSpacing: -0.2,
    color: colors.ink,
    textAlign: "center",
  },
  sub: { marginTop: 7, fontSize: 13, color: colors.ter, textAlign: "center", lineHeight: 19 },
});
