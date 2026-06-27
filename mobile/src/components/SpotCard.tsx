import { Pressable, Text, StyleSheet } from "react-native";
import { RemoteImage } from "@/components/RemoteImage";
import type { SpotCard as SpotCardDto } from "@/lib/api-types";
import { colors, radii } from "@/constants/theme";

interface SpotCardProps {
  spot: SpotCardDto;
  width?: number;
  onPress?: () => void;
  onPressIn?: () => void;
}

export function SpotCard({ spot, width = 185, onPress, onPressIn }: SpotCardProps) {
  return (
    <Pressable onPress={onPress} onPressIn={onPressIn} style={{ width }}>
      <RemoteImage
        uri={spot.firstImageUrl}
        radius={radii.md}
        style={{ width, height: width * 0.72 }}
      />
      <Text numberOfLines={1} style={styles.title}>
        {spot.title}
      </Text>
      {spot.category ? (
        <Text numberOfLines={1} style={styles.category}>
          {spot.category}
        </Text>
      ) : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  title: { marginTop: 8, fontSize: 15, fontWeight: "700", color: colors.ink },
  category: { marginTop: 3, fontSize: 13, color: colors.ter },
});
