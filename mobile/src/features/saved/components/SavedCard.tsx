import { Pressable, View, Text, StyleSheet } from "react-native";
import { RemoteImage } from "@/components/RemoteImage";
import { Icon } from "@/components/Icon";
import type { SpotCard } from "@/lib/api-types";
import { colors, radii } from "@/constants/theme";

interface Props {
  spot: SpotCard;
  onPress: () => void;
  onPressIn?: () => void;
  onUnsave: () => void;
}

export function SavedCard({ spot, onPress, onPressIn, onUnsave }: Props) {
  const region = spot.addr1?.trim().split(/\s+/)[0];
  const subline = [region, spot.category].filter(Boolean).join(" · ");

  return (
    <Pressable style={styles.card} onPress={onPress} onPressIn={onPressIn}>
      <RemoteImage uri={spot.firstImageUrl} style={styles.img} />
      <View style={styles.ov} pointerEvents="none" />
      <Pressable style={styles.heart} onPress={onUnsave} hitSlop={8}>
        <Icon name="heart-fill" size={19} color={colors.onImage} />
      </Pressable>
      <View style={styles.caption}>
        <Text numberOfLines={1} style={styles.name}>
          {spot.title}
        </Text>
        {subline ? (
          <Text numberOfLines={1} style={styles.sub}>
            {subline}
          </Text>
        ) : null}
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    width: "48.5%",
    height: 150,
    borderRadius: radii.md,
    overflow: "hidden",
    backgroundColor: colors.inset,
  },
  img: { width: "100%", height: "100%" },
  ov: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    height: "55%",
    backgroundColor: colors.scrim,
  },
  heart: {
    position: "absolute",
    top: 9,
    right: 9,
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: colors.control,
    alignItems: "center",
    justifyContent: "center",
  },
  caption: {
    position: "absolute",
    left: 12,
    right: 12,
    bottom: 11,
  },
  name: {
    color: colors.onImage,
    fontSize: 13,
    fontWeight: "600",
  },
  sub: {
    marginTop: 2,
    color: "rgba(255,255,255,0.8)",
    fontSize: 11,
  },
});
