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
        <Circle cx={23.5} cy={13} r={6.5} {...stroke} />
        <Path d="M23.5 19.5 V 40.5" {...stroke} />
        <Path d="M23.5 25 L 15.5 33.5" {...stroke} />
        <Path d="M23.5 25 L 33.5 21.5" {...stroke} />
        <Rect x={34.5} y={16} width={14.5} height={10.5} rx={2.5} {...stroke} />
        <Circle cx={41.75} cy={21.25} r={2.2} fill={color} />
        <Path d="M23.5 40.5 L 17.5 57" {...stroke} />
        <Path d="M23.5 40.5 L 29.5 57" {...stroke} />
      </Svg>
    </Animated.View>
  );
}
