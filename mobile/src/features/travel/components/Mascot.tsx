import { useEffect, useMemo } from "react";
import { Animated, Easing, type ColorValue } from "react-native";
import Svg, { Path, Circle, Rect } from "react-native-svg";
import { colors } from "@/constants/theme";

const FLOAT_HALF_MS = 2100;
const FLOAT_PX = 4;

interface Props {
  size?: number;
  color?: ColorValue;
  floating?: boolean;
}

export function Mascot({ size = 60, color = colors.ink, floating = true }: Props) {
  const drift = useMemo(() => new Animated.Value(0), []);

  useEffect(() => {
    if (!floating) return;
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(drift, {
          toValue: 1,
          duration: FLOAT_HALF_MS,
          easing: Easing.inOut(Easing.quad),
          useNativeDriver: true,
        }),
        Animated.timing(drift, {
          toValue: 0,
          duration: FLOAT_HALF_MS,
          easing: Easing.inOut(Easing.quad),
          useNativeDriver: true,
        }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [drift, floating]);

  const stroke = {
    stroke: color,
    strokeWidth: (size / 60) * 2.6,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    fill: "none" as const,
  };

  const translateY = drift.interpolate({
    inputRange: [0, 1],
    outputRange: [-FLOAT_PX, FLOAT_PX],
  });

  return (
    <Animated.View testID="travel-mascot" style={{ transform: [{ translateY }] }}>
      <Svg width={size} height={size} viewBox="0 0 64 64" fill="none">
        <Circle cx={32} cy={11} r={6.5} {...stroke} />
        <Path d="M32 17.5 V 26" {...stroke} />
        <Path d="M32 24 L 20 29" {...stroke} />
        <Path d="M32 24 L 44 29" {...stroke} />
        <Rect x={18.5} y={27} width={27} height={19} rx={3} {...stroke} />
        <Path d="M22 42 L 28.5 34.5 L 33 39 L 36.5 35.5 L 42 42" {...stroke} />
        <Path d="M27 46 L 25 58" {...stroke} />
        <Path d="M37 46 L 39 58" {...stroke} />
      </Svg>
    </Animated.View>
  );
}
