import type { ReactNode } from "react";
import {
  Image,
  StyleSheet,
  View,
  type ImageSourcePropType,
  type StyleProp,
  type ViewStyle,
} from "react-native";
import Svg, { Defs, LinearGradient, Rect, Stop } from "react-native-svg";

let gradientSeq = 0;

interface Props {
  source?: ImageSourcePropType;
  tones?: readonly [string, string];
  scrim?: "tile" | "card" | "none";
  style?: StyleProp<ViewStyle>;
  children?: ReactNode;
}

export function PreviewImage({
  source,
  tones = ["#2C3A4A", "#4A5A53"],
  scrim = "none",
  style,
  children,
}: Props) {
  const id = `onbPh${gradientSeq++}`;
  return (
    <View style={[styles.root, style]}>
      {source ? <Image source={source} style={styles.photo} resizeMode="cover" /> : null}
      <Svg style={StyleSheet.absoluteFill} width="100%" height="100%" pointerEvents="none">
        <Defs>
          <LinearGradient id={id} x1="0" y1="0" x2="1" y2="1">
            <Stop offset="0" stopColor={tones[0]} />
            <Stop offset="1" stopColor={tones[1]} />
          </LinearGradient>
          {scrim === "tile" ? (
            <LinearGradient id={`${id}s`} x1="0" y1="0" x2="0" y2="1">
              <Stop offset="0.34" stopColor="#100E12" stopOpacity={0} />
              <Stop offset="1" stopColor="#100E12" stopOpacity={0.7} />
            </LinearGradient>
          ) : (
            <LinearGradient id={`${id}s`} x1="0" y1="0" x2="0" y2="1">
              <Stop offset="0" stopColor="#0B0D11" stopOpacity={0.66} />
              <Stop offset="0.52" stopColor="#0B0D11" stopOpacity={0.04} />
              <Stop offset="1" stopColor="#0B0D11" stopOpacity={0.2} />
            </LinearGradient>
          )}
        </Defs>
        {source ? null : <Rect x="0" y="0" width="100%" height="100%" fill={`url(#${id})`} />}
        {scrim === "none" ? null : (
          <Rect x="0" y="0" width="100%" height="100%" fill={`url(#${id}s)`} />
        )}
      </Svg>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { overflow: "hidden" },
  photo: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    width: undefined,
    height: undefined,
  },
});
