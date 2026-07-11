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

export function SpotCard({ spot, width = 132, onPress, onPressIn }: SpotCardProps) {
  return (
    <Pressable onPress={onPress} onPressIn={onPressIn} style={{ width }}>
      <RemoteImage
        uri={spot.firstImageUrl}
        radius={radii.sm}
        style={{ width, height: width * (96 / 132) }}
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
  title: { marginTop: 7, fontSize: 13.5, fontWeight: "700", color: colors.ink },
  category: { marginTop: 2, fontSize: 12, color: colors.ter },
});
