import { useEffect, useMemo } from "react";
import { Animated, Easing, StyleSheet, View } from "react-native";
import { colors } from "@/constants/theme";

const CYCLE_MS = 1800;
const RING_SIZE = 220;

interface Props {
  active: boolean;
  bottom: number;
}

function Ring({ progress, delay }: { progress: Animated.Value; delay: number }) {
  const shifted = progress.interpolate({
    inputRange: [0, 1],
    outputRange: [delay, delay + 1],
  });
  const scale = shifted.interpolate({
    inputRange: [0, 0.5, 1, 1.5, 2],
    outputRange: [0.2, 0.7, 1.2, 0.7, 1.2],
  });
  const opacity = shifted.interpolate({
    inputRange: [0, 0.5, 1, 1.5, 2],
    outputRange: [0.65, 0.3, 0, 0.3, 0],
  });
  return <Animated.View style={[styles.ring, { opacity, transform: [{ scale }] }]} />;
}

export function SearchPulse({ active, bottom }: Props) {
  const progress = useMemo(() => new Animated.Value(0), []);

  useEffect(() => {
    if (!active) return;
    progress.setValue(0);
    const loop = Animated.loop(
      Animated.timing(progress, {
        toValue: 1,
        duration: CYCLE_MS,
        easing: Easing.linear,
        useNativeDriver: true,
      }),
    );
    loop.start();
    return () => loop.stop();
  }, [active, progress]);

  if (!active) return null;

  return (
    <View
      testID="travel-search-pulse"
      style={[styles.root, { bottom }]}
      pointerEvents="none"
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
    >
      <Ring progress={progress} delay={0} />
      <Ring progress={progress} delay={0.5} />
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    alignItems: "center",
    justifyContent: "center",
  },
  ring: {
    position: "absolute",
    width: RING_SIZE,
    height: RING_SIZE,
    borderRadius: RING_SIZE / 2,
    borderWidth: 1.6,
    borderColor: colors.accent,
  },
});
