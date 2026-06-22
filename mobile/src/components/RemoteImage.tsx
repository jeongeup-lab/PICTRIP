import { useState } from "react";
import { Image, View, type StyleProp, type ImageStyle, type ViewStyle } from "react-native";
import { colors } from "@/constants/theme";

interface RemoteImageProps {
  uri: string | null;
  style?: StyleProp<ImageStyle>;
  radius?: number;
}

export function RemoteImage({ uri, style, radius = 0 }: RemoteImageProps) {
  const [failed, setFailed] = useState(false);
  if (!uri || failed) {
    return (
      <View
        style={[
          { backgroundColor: colors.inset, borderRadius: radius } as ViewStyle,
          style as StyleProp<ViewStyle>,
        ]}
      />
    );
  }
  return (
    <Image
      source={{ uri }}
      onError={() => setFailed(true)}
      style={[{ borderRadius: radius }, style]}
    />
  );
}
