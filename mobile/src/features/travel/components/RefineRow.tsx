import { memo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { colors, radii, spacing } from "@/constants/theme";
import type { RefinePatch, Suggestion } from "@/features/travel/api";

interface Props {
  refinements: Suggestion[];
  onRefine: (patch: RefinePatch) => void;
}

function loosening(suggestion: Suggestion): boolean {
  return suggestion.patch.drop != null;
}

export const RETRY_LEAD = "다시 찾기";

export const RefineRow = memo(function RefineRow({ refinements, onRefine }: Props) {
  const loosen = refinements.filter(loosening);
  if (loosen.length === 0) return null;

  return (
    <View testID="travel-refinements" style={styles.root}>
      <Text style={styles.lead}>{RETRY_LEAD}</Text>
      <View style={styles.row}>
        {loosen.map((suggestion) => (
          <Pressable
            key={suggestion.label}
            accessibilityRole="button"
            accessibilityLabel={`${suggestion.label}, 눌러서 다시 찾기`}
            hitSlop={6}
            style={({ pressed }) => [styles.chip, pressed && styles.pressed]}
            onPress={() => onRefine(suggestion.patch)}
          >
            <Text style={styles.chipText}>{suggestion.label}</Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
});

const styles = StyleSheet.create({
  root: { gap: 7, paddingHorizontal: spacing.md },
  lead: {
    fontSize: 11.5,
    fontWeight: "600",
    letterSpacing: -0.2,
    color: colors.ter,
  },
  row: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
    alignItems: "center",
  },
  chip: {
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.glassBorder,
    backgroundColor: colors.raiseStrong,
  },
  chipText: {
    fontSize: 12,
    fontWeight: "600",
    letterSpacing: -0.1,
    color: colors.ink,
  },
  pressed: {
    opacity: 0.6,
  },
});
