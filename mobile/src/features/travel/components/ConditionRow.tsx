import { memo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { Icon } from "@/components/Icon";
import { colors } from "@/constants/theme";
import type { RefinePatch, Suggestion } from "@/features/travel/api";

interface Props {
  applied: string[];
  refinements: Suggestion[];
  onRefine: (patch: RefinePatch) => void;
}

function loosening(suggestion: Suggestion): boolean {
  return suggestion.patch.drop != null;
}

export const ConditionRow = memo(function ConditionRow({ applied, refinements, onRefine }: Props) {
  const loosen = refinements.filter(loosening);
  if (applied.length === 0 && loosen.length === 0) return null;

  return (
    <View testID="travel-conditions" style={styles.row}>
      {applied.map((label) => (
        <View key={`on-${label}`} style={styles.on}>
          <Text style={styles.onText}>{label}</Text>
        </View>
      ))}
      {loosen.map((suggestion) => (
        <Pressable
          key={`off-${suggestion.label}`}
          accessibilityRole="button"
          accessibilityLabel={`${suggestion.label}, 눌러서 조건 풀기`}
          hitSlop={6}
          style={({ pressed }) => [styles.off, pressed && styles.pressed]}
          onPress={() => onRefine(suggestion.patch)}
        >
          <Text style={styles.offText}>{suggestion.label}</Text>
          <Icon name="close" size={11} color={colors.ter} strokeWidth={2} />
        </Pressable>
      ))}
    </View>
  );
});

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
    alignItems: "center",
  },
  on: {
    paddingVertical: 5,
    paddingHorizontal: 10,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.fill,
  },
  onText: {
    fontSize: 12,
    fontWeight: "500",
    color: colors.ink,
  },
  off: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingVertical: 5,
    paddingHorizontal: 10,
    borderRadius: 999,
    borderWidth: 1,
    borderStyle: "dashed",
    borderColor: colors.line,
  },
  offText: {
    fontSize: 12,
    fontWeight: "500",
    color: colors.sec,
  },
  pressed: {
    opacity: 0.6,
  },
});
