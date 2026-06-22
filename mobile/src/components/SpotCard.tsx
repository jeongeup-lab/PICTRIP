import { Pressable, View, Text, StyleSheet } from "react-native";
import { RemoteImage } from "@/components/RemoteImage";
import { CongestionChip } from "@/components/CongestionChip";
import type { SpotCard as SpotCardDto } from "@/lib/api-types";
import { colors, radii } from "@/constants/theme";

interface SpotCardProps {
  spot: SpotCardDto;
  width?: number;
  onPress?: () => void;
}

export function SpotCard({ spot, width = 185, onPress }: SpotCardProps) {
  return (
    <Pressable onPress={onPress} style={{ width }}>
      <RemoteImage
        uri={spot.firstImageUrl}
        radius={radii.md}
        style={{ width, height: width * 0.72 }}
      />
      <Text numberOfLines={1} style={styles.title}>
        {spot.title}
      </Text>
      <View style={styles.meta}>
        {spot.category ? (
          <Text numberOfLines={1} style={styles.category}>
            {spot.category}
          </Text>
        ) : null}
        <CongestionChip level={spot.congestion ?? null} />
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  title: { marginTop: 8, fontSize: 15, fontWeight: "700", color: colors.ink },
  meta: { marginTop: 3, flexDirection: "row", alignItems: "center", gap: 8 },
  category: { fontSize: 13, color: colors.ter, flexShrink: 1 },
});
