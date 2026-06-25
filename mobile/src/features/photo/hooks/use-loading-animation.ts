import { useEffect, useMemo } from "react";
import { Animated, Easing } from "react-native";
import { LOADING_SWEEP_MS } from "@/features/photo/constants/timing";

export interface UseLoadingAnimation {
  /** Horizontal offset for the indeterminate bar fill. */
  translateX: Animated.AnimatedInterpolation<string | number>;
}

/**
 * Indeterminate progress-bar loop for the analyzing screen.
 *
 * Uses `useMemo` for the Animated.Value + interpolation (React 19 purity — no
 * useRef/interpolate during render); the looped timing lives in an effect that
 * stops on unmount.
 */
export function useLoadingAnimation(): UseLoadingAnimation {
  const anim = useMemo(() => new Animated.Value(0), []);

  useEffect(() => {
    const loop = Animated.loop(
      Animated.timing(anim, {
        toValue: 1,
        duration: LOADING_SWEEP_MS,
        easing: Easing.inOut(Easing.ease),
        useNativeDriver: true,
      }),
    );
    loop.start();
    return () => loop.stop();
  }, [anim]);

  const translateX = useMemo(
    () => anim.interpolate({ inputRange: [0, 1], outputRange: ["-42%", "100%"] }),
    [anim],
  );

  return { translateX };
}
