import { memo } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { colors, radii, spacing } from "@/constants/theme";
import { ANCHOR_CHOICES } from "@/features/travel/lib/anchor-actions";
import type { AnchorAction } from "@/features/travel/api";

interface Props {
  index: number;
  title: string;
  onAnchor: (action: AnchorAction, label: string) => void;
}

export const AnchorRow = memo(function AnchorRow({ index, title, onAnchor }: Props) {
  return (
    <View testID="travel-anchor-row" style={styles.root}>
      <View style={styles.lead}>
        <View style={styles.badge}>
          <Text style={styles.badgeText}>{index + 1}</Text>
        </View>
        <Text testID="travel-anchor-title" style={styles.title} numberOfLines={1}>
          {title}
        </Text>
      </View>

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.chips}
      >
        {ANCHOR_CHOICES.map((choice) => (
          <Pressable
            key={choice.action}
            testID={`travel-anchor-${choice.action}`}
            accessibilityRole="button"
            accessibilityLabel={`${title} ${choice.label}`}
            hitSlop={6}
            style={({ pressed }) => [styles.chip, pressed && styles.pressed]}
            onPress={() => onAnchor(choice.action, choice.label)}
          >
            <Text style={styles.chipText}>{choice.label}</Text>
          </Pressable>
        ))}
      </ScrollView>
    </View>
  );
});

const styles = StyleSheet.create({
  root: { gap: 8 },
  lead: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: spacing.md,
  },
  badge: {
    width: 17,
    height: 17,
    borderRadius: 9,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.accent,
  },
  badgeText: { fontSize: 10, fontWeight: "800", color: colors.onImage },
  title: {
    flexShrink: 1,
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: -0.2,
    color: colors.ink,
  },
  chips: { flexDirection: "row", gap: 6, paddingHorizontal: spacing.md },
  chip: {
    paddingVertical: 6,
    paddingHorizontal: 11,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.glassBorder,
    backgroundColor: colors.raiseStrong,
  },
  chipText: { fontSize: 12, fontWeight: "600", letterSpacing: -0.1, color: colors.ink },
  pressed: { opacity: 0.6 },
});
