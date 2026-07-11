import { Pressable, View, Text, StyleSheet } from "react-native";
import { RemoteImage } from "@/components/RemoteImage";
import { Icon } from "@/components/Icon";
import { formatDistance } from "@/lib/distance";
import type { NearbySpot } from "@/lib/api-types";
import { colors, spacing, radii } from "@/constants/theme";

interface Props {
  spot: NearbySpot;
  selected?: boolean;
  onPress: () => void;
  onPressIn?: () => void;
}

export function NearbyCard({ spot, selected, onPress, onPressIn }: Props) {
  const metaPrefix = [spot.sigunguName, spot.category].filter(Boolean).join(" · ");
  const distText = spot.dist != null ? formatDistance(spot.dist) : null;
  const hasMeta = metaPrefix.length > 0 || distText != null;

  return (
    <Pressable
      onPress={onPress}
      onPressIn={onPressIn}
      style={[styles.card, selected && styles.selected]}
    >
      <RemoteImage uri={spot.firstImageUrl} radius={radii.md} style={styles.img} />
      <View style={styles.body}>
        <Text numberOfLines={1} style={styles.title}>
          {spot.title}
        </Text>
        {hasMeta ? (
          <View style={styles.metaRow}>
            <Icon name="map-pin" size={13} color={colors.ter} />
            <Text numberOfLines={1} style={styles.meta}>
              {metaPrefix}
              {metaPrefix && distText ? " · " : ""}
              {distText ? <Text style={styles.dist}>{distText}</Text> : null}
            </Text>
          </View>
        ) : null}
        {spot.overview ? (
          <Text numberOfLines={1} style={styles.overview}>
            {spot.overview}
          </Text>
        ) : null}
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: "row",
    gap: 12,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
  },
  selected: { backgroundColor: colors.fill },
  img: { width: 86, height: 86, borderRadius: radii.md, backgroundColor: colors.inset },
  body: { flex: 1, justifyContent: "center", minWidth: 0 },
  title: { fontSize: 16, fontWeight: "700", color: colors.ink },
  metaRow: { flexDirection: "row", alignItems: "center", gap: 4, marginTop: 4 },
  meta: { flex: 1, fontSize: 12.5, color: colors.ter },
  dist: { color: colors.accentText, fontWeight: "700" },
  overview: { fontSize: 12.5, color: colors.sec, marginTop: 4 },
});
