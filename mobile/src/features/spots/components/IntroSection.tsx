import { useMemo, useState } from "react";
import { View, Text, Pressable, StyleSheet } from "react-native";
import { htmlToPlainText } from "@/lib/html-text";
import { colors, spacing } from "@/constants/theme";

export function IntroSection({ overview }: { overview: string | null }) {
  const [expanded, setExpanded] = useState(false);
  const text = useMemo(() => (overview ? htmlToPlainText(overview) : ""), [overview]);
  if (!text) return null;
  return (
    <View style={styles.section}>
      <Text style={styles.h2}>소개</Text>
      <Text style={styles.overview} numberOfLines={expanded ? undefined : 5}>
        {text}
      </Text>
      <Pressable onPress={() => setExpanded((v) => !v)} hitSlop={6}>
        <Text style={styles.moreText}>{expanded ? "접기" : "더보기"}</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  section: { paddingHorizontal: spacing.lg, paddingTop: 24 },
  h2: {
    fontSize: 19,
    fontWeight: "800",
    letterSpacing: -0.4,
    color: colors.ink,
    marginBottom: 12,
  },
  overview: { fontSize: 14.5, lineHeight: 23, color: colors.sec },
  moreText: { fontSize: 13, fontWeight: "700", color: colors.accentText, marginTop: 12 },
});
