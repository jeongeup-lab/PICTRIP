import { useState } from "react";
import {
  View,
  Text,
  Pressable,
  StyleSheet,
  type NativeSyntheticEvent,
  type TextLayoutEventData,
} from "react-native";
import { Icon } from "@/components/Icon";
import { colors, spacing } from "@/constants/theme";

const CLAMP_LINES = 3;

/** Detail intro copy (S02 §06-6·7): renders unclamped once to measure the line
 * count, then clamps to 3 lines with a chevron expand/collapse toggle. The
 * chevron stays hidden when the intro fits within 3 lines. */
export function CurationIntro({ intro }: { intro: string }) {
  const [expanded, setExpanded] = useState(false);
  const [lineCount, setLineCount] = useState<number | null>(null);

  const measured = lineCount !== null;
  const canExpand = (lineCount ?? 0) > CLAMP_LINES;

  const onTextLayout = (e: NativeSyntheticEvent<TextLayoutEventData>) => {
    if (!measured) {
      setLineCount(e.nativeEvent.lines.length);
    }
  };

  return (
    <View>
      <Text
        style={styles.intro}
        numberOfLines={measured && canExpand && !expanded ? CLAMP_LINES : undefined}
        onTextLayout={onTextLayout}
      >
        {intro}
      </Text>
      {canExpand ? (
        <Pressable
          testID="intro-toggle"
          accessibilityRole="button"
          accessibilityLabel={expanded ? "본문 접기" : "본문 더보기"}
          hitSlop={10}
          onPress={() => setExpanded((v) => !v)}
          style={styles.chevron}
        >
          <View style={expanded ? styles.flipped : undefined}>
            <Icon name="chevron-down" size={26} color={colors.ter} />
          </View>
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  intro: {
    fontSize: 14,
    color: colors.sec,
    lineHeight: 22,
    paddingHorizontal: 16,
    marginTop: spacing.sm,
  },
  chevron: { alignItems: "center", marginTop: spacing.lg },
  flipped: { transform: [{ rotate: "180deg" }] },
});
