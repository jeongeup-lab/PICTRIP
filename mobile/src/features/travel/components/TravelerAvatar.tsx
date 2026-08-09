import { View, StyleSheet } from "react-native";
import Svg, { Circle, Path } from "react-native-svg";
import { colors } from "@/constants/theme";

const STICK_PATHS = [
  "M12 10.5V16",
  "M12 12.5L7.5 15",
  "M12 12.5L16.5 15",
  "M12 16L9 21",
  "M12 16L15 21",
];

export function TravelerAvatar() {
  return (
    <View style={styles.circle}>
      <Svg width={20} height={20} viewBox="0 0 24 24" fill="none">
        <Circle
          cx={12}
          cy={6.5}
          r={3.6}
          stroke={colors.ink}
          strokeWidth={1.9}
          strokeLinecap="round"
        />
        {STICK_PATHS.map((d) => (
          <Path key={d} d={d} stroke={colors.ink} strokeWidth={1.9} strokeLinecap="round" />
        ))}
      </Svg>
    </View>
  );
}

const styles = StyleSheet.create({
  circle: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: colors.fillStrong,
    alignItems: "center",
    justifyContent: "center",
  },
});
