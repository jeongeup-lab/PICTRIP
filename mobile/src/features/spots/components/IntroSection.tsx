import { useState } from "react";
import { View, Text, Pressable, StyleSheet } from "react-native";
import { colors, spacing } from "@/constants/theme";

/** Renders KTO overview verbatim; clamp is visual only (never alters text). */
export function IntroSection({ overview }: { overview: string | null }) {
  const [expanded, setExpanded] = useState(false);
  if (!overview) return null;
  return (
    <View style={styles.section}>
      <Text style={styles.body} numberOfLines={expanded ? undefined : 4}>
        {overview}
      </Text>
      <Pressable onPress={() => setExpanded((v) => !v)} hitSlop={6}>
        <Text style={styles.toggle}>{expanded ? "접기" : "더보기"}</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  section: { paddingHorizontal: spacing.lg, marginTop: spacing.lg },
  body: { fontSize: 15, lineHeight: 24, color: colors.sec },
  toggle: { marginTop: spacing.xs, fontSize: 14, fontWeight: "700", color: colors.ink },
});
