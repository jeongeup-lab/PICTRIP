import { useEffect, useMemo } from "react";
import { Animated, Easing, View, Text, StyleSheet } from "react-native";
import { Icon } from "@/components/Icon";
import type { AgentStep } from "@/features/travel/api";
import { colors } from "@/constants/theme";

const SPIN_MS = 700;

function Spinner() {
  const spin = useMemo(() => new Animated.Value(0), []);

  useEffect(() => {
    const loop = Animated.loop(
      Animated.timing(spin, {
        toValue: 1,
        duration: SPIN_MS,
        easing: Easing.linear,
        useNativeDriver: true,
      }),
    );
    loop.start();
    return () => loop.stop();
  }, [spin]);

  const rotate = spin.interpolate({ inputRange: [0, 1], outputRange: ["0deg", "360deg"] });
  return (
    <Animated.View testID="step-spinner" style={[styles.spinner, { transform: [{ rotate }] }]} />
  );
}

interface Props {
  steps: AgentStep[];
  shown: number;
  completed: number;
}

export function StepList({ steps, shown, completed }: Props) {
  return (
    <View>
      {steps.slice(0, shown).map((step, index) => (
        <View key={`${step.tool}-${index}`} style={[styles.row, index > 0 && styles.divider]}>
          <View style={styles.mark}>
            {index < completed ? (
              <Icon name="check" size={15} color={colors.accentText} strokeWidth={2.4} />
            ) : (
              <Spinner />
            )}
          </View>
          <Text style={styles.label} numberOfLines={1}>
            {step.label}
          </Text>
          {step.badge ? (
            <View style={styles.badge}>
              <Text style={styles.badgeText}>{step.badge}</Text>
            </View>
          ) : null}
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", gap: 9, paddingVertical: 8 },
  divider: { borderTopWidth: 1, borderTopColor: colors.line },
  mark: { width: 15, height: 15, alignItems: "center", justifyContent: "center" },
  spinner: {
    width: 14,
    height: 14,
    borderRadius: 7,
    borderWidth: 2,
    borderColor: colors.line,
    borderTopColor: colors.accent,
  },
  label: { flex: 1, fontSize: 13, letterSpacing: -0.2, color: colors.sec },
  badge: {
    paddingVertical: 3,
    paddingHorizontal: 7,
    borderRadius: 6,
    backgroundColor: colors.accentFill,
  },
  badgeText: { fontSize: 11, fontWeight: "700", color: colors.accentText },
});
