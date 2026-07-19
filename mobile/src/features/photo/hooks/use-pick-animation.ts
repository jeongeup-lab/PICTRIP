import { useEffect, useMemo, useRef, useState } from "react";
import { AccessibilityInfo, Animated, Easing } from "react-native";
import {
  FINALE_HOLD_MS,
  FINALE_HOP_MS,
  HOP_MS,
} from "@/features/photo/constants/timing";

type Status = "idle" | "loading" | "success" | "error";

export interface CardSlot {
  x: number;
  y: number;
  rotate: number;
  hero?: boolean;
}

const CARD_SLOTS: CardSlot[] = [
  { x: -76, y: -44, rotate: -7 },
  { x: 64, y: -54, rotate: 6 },
  { x: -66, y: 46, rotate: 5 },
  { x: 70, y: 42, rotate: -6 },
  { x: -2, y: -4, rotate: 0, hero: true },
];

const HERO_INDEX = 4;
const HOP_ORDER = [0, 3, 1, 2, 0, 2, 3, 1];

export interface UsePickAnimation {
  cards: CardSlot[];
  reduceMotion: boolean;
  figureX: Animated.Value;
  figureY: Animated.Value;
  figureArc: Animated.AnimatedInterpolation<number>;
  standOpacity: Animated.AnimatedInterpolation<number>;
  leapOpacity: Animated.AnimatedInterpolation<number>;
  heroOpacity: Animated.Value;
}

/**
 * Choreographs the stick figure hopping between candidate photo cards while
 * `status === "loading"`, then closes on the hero card and holds the finale
 * pose once `status === "success"`. `onFinaleComplete` fires after the finale
 * hold so the caller can navigate away.
 *
 * Falls back to a static finale pose (no loop) when the OS reports reduced
 * motion.
 */
export function usePickAnimation(status: Status, onFinaleComplete: () => void): UsePickAnimation {
  const [reduceMotion, setReduceMotion] = useState(false);

  useEffect(() => {
    let mounted = true;
    AccessibilityInfo.isReduceMotionEnabled().then((value) => {
      if (mounted) setReduceMotion(value);
    });
    const sub = AccessibilityInfo.addEventListener("reduceMotionChanged", setReduceMotion);
    return () => {
      mounted = false;
      sub.remove();
    };
  }, []);

  const figureX = useMemo(() => new Animated.Value(CARD_SLOTS[HOP_ORDER[0]].x), []);
  const figureY = useMemo(() => new Animated.Value(CARD_SLOTS[HOP_ORDER[0]].y), []);
  const hopT = useMemo(() => new Animated.Value(0), []);
  const heroOpacity = useMemo(() => new Animated.Value(0), []);

  const stepRef = useRef(0);
  const stoppedRef = useRef(false);
  const onFinaleCompleteRef = useRef(onFinaleComplete);
  useEffect(() => {
    onFinaleCompleteRef.current = onFinaleComplete;
  }, [onFinaleComplete]);

  useEffect(() => {
    stoppedRef.current = false;
    let finaleTimer: ReturnType<typeof setTimeout> | undefined;

    if (reduceMotion) {
      const hero = CARD_SLOTS[HERO_INDEX];
      figureX.setValue(hero.x);
      figureY.setValue(hero.y);
      hopT.setValue(1);
      if (status === "success") {
        heroOpacity.setValue(1);
        onFinaleCompleteRef.current();
      }
      return;
    }

    if (status === "loading") {
      let current: Animated.CompositeAnimation | undefined;
      const hop = () => {
        if (stoppedRef.current) return;
        stepRef.current += 1;
        const target = CARD_SLOTS[HOP_ORDER[stepRef.current % HOP_ORDER.length]];
        hopT.setValue(0);
        current = Animated.parallel([
          Animated.timing(figureX, {
            toValue: target.x,
            duration: HOP_MS,
            easing: Easing.inOut(Easing.quad),
            useNativeDriver: false,
          }),
          Animated.timing(figureY, {
            toValue: target.y,
            duration: HOP_MS,
            easing: Easing.inOut(Easing.quad),
            useNativeDriver: false,
          }),
          Animated.timing(hopT, {
            toValue: 1,
            duration: HOP_MS,
            easing: Easing.linear,
            useNativeDriver: false,
          }),
        ]);
        current.start(({ finished }) => {
          if (finished) hop();
        });
      };
      hop();
      return () => {
        stoppedRef.current = true;
        current?.stop();
      };
    }

    if (status === "success") {
      stoppedRef.current = true;
      const hero = CARD_SLOTS[HERO_INDEX];
      hopT.setValue(0);
      const finale = Animated.parallel([
        Animated.timing(figureX, {
          toValue: hero.x,
          duration: FINALE_HOP_MS,
          easing: Easing.out(Easing.cubic),
          useNativeDriver: false,
        }),
        Animated.timing(figureY, {
          toValue: hero.y,
          duration: FINALE_HOP_MS,
          easing: Easing.out(Easing.cubic),
          useNativeDriver: false,
        }),
        Animated.timing(hopT, {
          toValue: 1,
          duration: FINALE_HOP_MS,
          easing: Easing.linear,
          useNativeDriver: false,
        }),
        Animated.timing(heroOpacity, {
          toValue: 1,
          duration: FINALE_HOP_MS,
          easing: Easing.out(Easing.quad),
          useNativeDriver: false,
        }),
      ]);
      finale.start(({ finished }) => {
        if (!finished) return;
        finaleTimer = setTimeout(() => onFinaleCompleteRef.current(), FINALE_HOLD_MS);
      });
      return () => {
        finale.stop();
        if (finaleTimer) clearTimeout(finaleTimer);
      };
    }

    stoppedRef.current = true;
    return undefined;
  }, [status, reduceMotion, figureX, figureY, hopT, heroOpacity]);

  const figureArc = useMemo(
    () => hopT.interpolate({ inputRange: [0, 0.5, 1], outputRange: [0, -30, 0] }),
    [hopT],
  );
  const standOpacity = useMemo(
    () => hopT.interpolate({ inputRange: [0, 0.18, 0.82, 1], outputRange: [1, 0, 0, 1] }),
    [hopT],
  );
  const leapOpacity = useMemo(
    () => hopT.interpolate({ inputRange: [0, 0.18, 0.82, 1], outputRange: [0, 1, 1, 0] }),
    [hopT],
  );

  return {
    cards: CARD_SLOTS,
    reduceMotion,
    figureX,
    figureY,
    figureArc,
    standOpacity,
    leapOpacity,
    heroOpacity,
  };
}
