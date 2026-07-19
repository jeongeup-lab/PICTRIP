import { Animated, StyleSheet } from "react-native";
import Svg, { Circle, Path, Rect } from "react-native-svg";
import { colors } from "@/constants/theme";

interface StickFigureProps {
  size?: number;
  standOpacity: Animated.AnimatedInterpolation<number>;
  leapOpacity: Animated.AnimatedInterpolation<number>;
}

const STROKE = 1.8;

/**
 * The PicTrip mark — a stick figure holding a camera — as two crossfading
 * poses: "stand" (matches assets/icon.png, used at rest and the finale) and
 * "leap" (mid-jump reach, used while hopping between candidate photos).
 */
export function StickFigure({ size = 96, standOpacity, leapOpacity }: StickFigureProps) {
  return (
    <>
      <Animated.View style={[styles.layer, { opacity: standOpacity }]}>
        <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
          <Circle cx={10} cy={5} r={2.5} stroke={colors.ink} strokeWidth={STROKE} />
          <Path d="M10 7.5L11 15" stroke={colors.ink} strokeWidth={STROKE} strokeLinecap="round" />
          <Path
            d="M10.3 9L16.2 6.8"
            stroke={colors.ink}
            strokeWidth={STROKE}
            strokeLinecap="round"
          />
          <Rect
            x={15.6}
            y={5}
            width={3.6}
            height={2.6}
            rx={0.8}
            stroke={colors.ink}
            strokeWidth={STROKE * 0.9}
          />
          <Circle cx={17.6} cy={6.3} r={0.65} fill={colors.accent} />
          <Path
            d="M10.2 10L7.4 13.4"
            stroke={colors.ink}
            strokeWidth={STROKE}
            strokeLinecap="round"
          />
          <Path d="M11 15L8.2 21" stroke={colors.ink} strokeWidth={STROKE} strokeLinecap="round" />
          <Path
            d="M11 15L13.8 21"
            stroke={colors.ink}
            strokeWidth={STROKE}
            strokeLinecap="round"
          />
        </Svg>
      </Animated.View>

      <Animated.View style={[styles.layer, { opacity: leapOpacity }]}>
        <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
          <Circle cx={11.5} cy={4.6} r={2.5} stroke={colors.ink} strokeWidth={STROKE} />
          <Path
            d="M11.5 7.1L12.3 13.5"
            stroke={colors.ink}
            strokeWidth={STROKE}
            strokeLinecap="round"
          />
          <Path
            d="M11.8 8.6L18.2 4.6"
            stroke={colors.ink}
            strokeWidth={STROKE}
            strokeLinecap="round"
          />
          <Rect
            x={17.6}
            y={2.8}
            width={3.6}
            height={2.6}
            rx={0.8}
            stroke={colors.ink}
            strokeWidth={STROKE * 0.9}
          />
          <Circle cx={19.6} cy={4.1} r={0.65} fill={colors.accent} />
          <Path
            d="M11.9 9.4L6.4 11.2"
            stroke={colors.ink}
            strokeWidth={STROKE}
            strokeLinecap="round"
          />
          <Path
            d="M12.3 13.5L16.6 19.4"
            stroke={colors.ink}
            strokeWidth={STROKE}
            strokeLinecap="round"
          />
          <Path
            d="M12.3 13.5L7 18.6"
            stroke={colors.ink}
            strokeWidth={STROKE}
            strokeLinecap="round"
          />
        </Svg>
      </Animated.View>
    </>
  );
}

const styles = StyleSheet.create({
  layer: { position: "absolute", left: 0, top: 0 },
});
