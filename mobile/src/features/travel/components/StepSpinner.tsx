import { useEffect, useState } from "react";
import { Animated, Easing, StyleSheet } from "react-native";
import { colors } from "@/constants/theme";

export const SPINNER_TEST_ID = "travel-step-spinner";
export const SPIN_DURATION_MS = 900;
export const SPINNER_LABEL = "진행 중";

const DEFAULT_SIZE = 13;

export function StepSpinner({ size = DEFAULT_SIZE }: { size?: number }) {
  const [turn] = useState(() => new Animated.Value(0));

  useEffect(() => {
    const loop = Animated.loop(
      Animated.timing(turn, {
        toValue: 1,
        duration: SPIN_DURATION_MS,
        easing: Easing.linear,
        useNativeDriver: true,
      }),
    );
    loop.start();
    return () => loop.stop();
  }, [turn]);

  const rotate = turn.interpolate({ inputRange: [0, 1], outputRange: ["0deg", "360deg"] });

  return (
    <Animated.View
      testID={SPINNER_TEST_ID}
      accessibilityRole="progressbar"
      accessibilityLabel={SPINNER_LABEL}
      style={[
        styles.ring,
        { width: size, height: size, borderRadius: size / 2 },
        { transform: [{ rotate }] },
      ]}
    />
  );
}

const styles = StyleSheet.create({
  ring: {
    borderWidth: 2,
    borderColor: colors.line,
    borderTopColor: colors.accent,
  },
});
