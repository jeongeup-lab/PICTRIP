import { useMemo, useState } from "react";
import { View, Text, Pressable, StyleSheet } from "react-native";
import { Icon } from "@/components/Icon";
import { htmlToPlainText } from "@/lib/html-text";
import { colors, spacing } from "@/constants/theme";

/** 소개 section. Renders KTO overview text; HTML tags/entities are stripped for
 * display only (the stored value is untouched), clamp is visual only. */
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
      <Pressable style={styles.more} onPress={() => setExpanded((v) => !v)} hitSlop={6}>
        <Text style={styles.moreText}>{expanded ? "접기" : "더보기"}</Text>
        <Icon name="chevron-down" size={18} color={colors.ink} />
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  section: { paddingHorizontal: spacing.lg, paddingTop: 30 },
  h2: {
    fontSize: 22,
    fontWeight: "800",
    letterSpacing: -0.44,
    color: colors.ink,
    marginBottom: 16,
  },
  overview: { fontSize: 15.5, lineHeight: 26, color: colors.sec },
  more: { flexDirection: "row", alignItems: "center", gap: 2, marginTop: 11 },
  moreText: { fontSize: 15, fontWeight: "700", color: colors.ink },
});
