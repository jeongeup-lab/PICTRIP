import { View, type ViewStyle, type StyleProp } from "react-native";
import { colors } from "@/constants/theme";

interface SkeletonProps {
  width?: number | `${number}%`;
  height?: number;
  radius?: number;
  style?: StyleProp<ViewStyle>;
}

export function Skeleton({ width = "100%", height = 16, radius = 8, style }: SkeletonProps) {
  return (
    <View
      style={[{ width, height, borderRadius: radius, backgroundColor: colors.skeleton }, style]}
    />
  );
}
