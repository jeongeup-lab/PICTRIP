import { Pressable, StyleSheet, Text, View } from "react-native";
import Svg, { Defs, LinearGradient, Rect, Stop } from "react-native-svg";
import { Icon } from "@/components/Icon";
import { RemoteImage } from "@/components/RemoteImage";
import type { ShortsCardData } from "@/features/shorts/api";
import { formatViews } from "@/features/shorts/lib/format-views";
import { colors, radii, spacing } from "@/constants/theme";

export const SHORTS_CARD_HEIGHT = 520;

interface Props {
  short: ShortsCardData;
  onOpen: (short: ShortsCardData) => void;
}

export function ShortsCard({ short, onOpen }: Props) {
  return (
    <Pressable testID="shorts-card" style={styles.card} onPress={() => onOpen(short)}>
      <RemoteImage uri={short.thumbnailUrl} style={StyleSheet.absoluteFill} />
      <Svg style={StyleSheet.absoluteFill} width="100%" height="100%" pointerEvents="none">
        <Defs>
          <LinearGradient id="shortsScrim" x1="0" y1="0" x2="0" y2="1">
            <Stop offset="0" stopColor="#141216" stopOpacity={0.35} />
            <Stop offset="0.3" stopColor="#141216" stopOpacity={0} />
            <Stop offset="0.55" stopColor="#141216" stopOpacity={0} />
            <Stop offset="1" stopColor="#141216" stopOpacity={0.78} />
          </LinearGradient>
        </Defs>
        <Rect x="0" y="0" width="100%" height="100%" fill="url(#shortsScrim)" />
      </Svg>

      <View style={styles.anchorChip}>
        <Icon name="map-pin" size={13} color={colors.accentText} strokeWidth={2.4} />
        <Text style={styles.anchorText}>{short.anchorLabel}</Text>
      </View>

      <View style={styles.playBadge} pointerEvents="none">
        <Icon name="play" size={22} color={colors.onImage} />
      </View>

      <View style={styles.meta} pointerEvents="none">
        <Text style={styles.title} numberOfLines={2}>
          {short.title}
        </Text>
        <View style={styles.metaRow}>
          {short.spots.length > 0 ? (
            <View style={styles.spotsPill}>
              <Icon name="map-pin" size={11} color={colors.accentText} strokeWidth={2.4} />
              <Text style={styles.spotsPillText}>스팟 {short.spots.length}곳</Text>
            </View>
          ) : null}
          <Text style={styles.channel} numberOfLines={1}>
            {short.channelTitle}
          </Text>
          <Text style={styles.views}>조회수 {formatViews(short.viewCount)}</Text>
        </View>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    height: SHORTS_CARD_HEIGHT,
    marginHorizontal: spacing.md + 2,
    borderRadius: radii.lg + 4,
    overflow: "hidden",
    backgroundColor: colors.inset,
  },
  anchorChip: {
    position: "absolute",
    top: spacing.md,
    left: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    paddingVertical: 6,
    paddingLeft: 9,
    paddingRight: 12,
    borderRadius: radii.pill,
    backgroundColor: colors.glassFill,
    borderWidth: 1,
    borderColor: colors.glassBorder,
  },
  anchorText: { fontSize: 12.5, fontWeight: "800", color: colors.onImage },
  playBadge: {
    position: "absolute",
    top: "50%",
    left: "50%",
    marginTop: -28,
    marginLeft: -28,
    width: 56,
    height: 56,
    borderRadius: 28,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.control,
    borderWidth: 1,
    borderColor: colors.glassBorder,
  },
  meta: {
    position: "absolute",
    left: spacing.lg - 4,
    right: spacing.lg - 4,
    bottom: spacing.lg - 4,
    gap: 6,
  },
  title: { fontSize: 15, fontWeight: "700", lineHeight: 20, color: colors.onImage },
  metaRow: { flexDirection: "row", alignItems: "center", gap: spacing.xs },
  spotsPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingVertical: 2,
    paddingHorizontal: 8,
    borderRadius: radii.pill,
    backgroundColor: colors.accentFill,
  },
  spotsPillText: { fontSize: 11, fontWeight: "800", color: colors.accentText },
  channel: { flexShrink: 1, fontSize: 12, color: colors.onDim },
  views: { fontSize: 12, color: colors.onDim },
});
