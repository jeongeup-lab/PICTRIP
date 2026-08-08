import { useMemo, useState } from "react";
import { View, Text, Pressable, StyleSheet, type TextLayoutEvent } from "react-native";
import { htmlToPlainText } from "@/lib/html-text";
import { colors, spacing } from "@/constants/theme";

const COLLAPSED_LINES = 5;

export function IntroSection({ overview }: { overview: string | null }) {
  const [expanded, setExpanded] = useState(false);
  const [overflowingText, setOverflowingText] = useState<string | null>(null);
  const text = useMemo(() => (overview ? htmlToPlainText(overview) : ""), [overview]);
  if (!text) return null;

  const handleMeasure = (event: TextLayoutEvent) => {
    setOverflowingText(event.nativeEvent.lines.length > COLLAPSED_LINES ? text : null);
  };

  return (
    <View style={styles.section}>
      <Text style={styles.h2}>소개</Text>
      <View>
        <Text style={styles.overview} numberOfLines={expanded ? undefined : COLLAPSED_LINES}>
          {text}
        </Text>
        <View
          style={styles.measureLayer}
          pointerEvents="none"
          accessibilityElementsHidden
          importantForAccessibility="no-hide-descendants"
        >
          <Text
            testID="intro-measure"
            style={styles.overview}
            numberOfLines={COLLAPSED_LINES + 1}
            onTextLayout={handleMeasure}
          >
            {text}
          </Text>
        </View>
      </View>
      {overflowingText === text ? (
        <Pressable onPress={() => setExpanded((v) => !v)} hitSlop={6}>
          <Text style={styles.moreText}>{expanded ? "접기" : "더보기"}</Text>
        </Pressable>
      ) : null}
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
  measureLayer: { position: "absolute", top: 0, left: 0, right: 0, opacity: 0 },
  moreText: { fontSize: 13, fontWeight: "700", color: colors.accentText, marginTop: 12 },
});
