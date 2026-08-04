import { Pressable, View, Text, StyleSheet, type StyleProp, type ViewStyle } from "react-native";
import Svg, { Defs, LinearGradient, Stop, Rect } from "react-native-svg";
import { router } from "expo-router";
import { RemoteImage } from "@/components/RemoteImage";
import { Icon } from "@/components/Icon";
import { useSaveOptimistic } from "@/features/saved/hooks/use-save-optimistic";
import { prefetchSpot } from "@/features/spots/queries";
import type { TravelSpot } from "@/features/travel/api";
import { colors } from "@/constants/theme";

export const RAIL_CARD_WIDTH = 158;
export const RAIL_CARD_HEIGHT = 206;
export const MEDIA_HEIGHT = 172;

export const ANCHOR_ACTION_LABEL = "여기 기준으로";

interface Props {
  spot: TravelSpot;
  style?: StyleProp<ViewStyle>;
  onSaveToggle?: (saved: boolean) => void;
  onPress?: () => void;
  onAnchor?: () => void;
  selected?: boolean;
  dimmed?: boolean;
}

export function SpotCard({
  spot,
  style,
  onSaveToggle,
  onPress,
  onAnchor,
  selected,
  dimmed,
}: Props) {
  const { saved, toggle } = useSaveOptimistic(spot.contentId);

  return (
    <View style={[styles.card, style, dimmed && styles.dimmed]}>
      <Pressable
        testID={`travel-spot-${spot.contentId}`}
        style={({ pressed }) => [styles.media, pressed && styles.pressed]}
        onPressIn={() => prefetchSpot(spot)}
        onPress={onPress ?? (() => router.push(`/spots/${spot.contentId}`))}
      >
        <RemoteImage uri={spot.imageUrl} style={StyleSheet.absoluteFill} />
        <Svg style={StyleSheet.absoluteFill} width="100%" height="100%" pointerEvents="none">
          <Defs>
            <LinearGradient id="travelCardScrim" x1="0" y1="0" x2="0" y2="1">
              <Stop offset="0" stopColor="#141216" stopOpacity={0.16} />
              <Stop offset="0.32" stopColor="#141216" stopOpacity={0} />
              <Stop offset="0.46" stopColor="#100E12" stopOpacity={0} />
              <Stop offset="1" stopColor="#100E12" stopOpacity={0.8} />
            </LinearGradient>
          </Defs>
          <Rect x="0" y="0" width="100%" height="100%" fill="url(#travelCardScrim)" />
        </Svg>
        <View style={styles.hairline} pointerEvents="none" />

        {spot.tag ? (
          <View style={styles.tag}>
            <Text style={styles.tagText}>{spot.tag}</Text>
          </View>
        ) : null}

        <Pressable
          testID={`travel-spot-save-${spot.contentId}`}
          accessibilityLabel="저장"
          style={[styles.fav, saved && styles.favOn]}
          hitSlop={8}
          onPress={(e) => {
            e.stopPropagation();
            onSaveToggle?.(!saved);
            void toggle();
          }}
        >
          <Icon
            name={saved ? "heart-fill" : "heart"}
            size={14}
            color={colors.onImage}
            strokeWidth={1.9}
          />
        </Pressable>

        <View style={styles.caption}>
          <Text style={styles.title} numberOfLines={1}>
            {spot.title}
          </Text>
          <Text style={styles.region} numberOfLines={1}>
            {spot.regionLabel}
          </Text>
        </View>
      </Pressable>

      {onAnchor ? (
        <Pressable
          testID={`travel-spot-anchor-${spot.contentId}`}
          accessibilityRole="button"
          style={({ pressed }) => [
            styles.anchor,
            selected && styles.anchorOn,
            pressed && styles.anchorPressed,
          ]}
          onPress={onAnchor}
        >
          <Icon
            name="location"
            size={12}
            color={selected ? colors.accentText : colors.sec}
            strokeWidth={2.1}
          />
          <Text style={[styles.anchorText, selected && styles.anchorTextOn]}>
            {ANCHOR_ACTION_LABEL}
          </Text>
        </Pressable>
      ) : null}

      {selected ? <View style={styles.selectedRing} pointerEvents="none" /> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    width: RAIL_CARD_WIDTH,
    height: RAIL_CARD_HEIGHT,
    borderRadius: 16,
    overflow: "hidden",
    backgroundColor: colors.skeleton,
  },
  media: { height: MEDIA_HEIGHT },
  anchor: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 5,
    borderTopWidth: 1,
    borderTopColor: colors.line,
    backgroundColor: colors.inset,
  },
  anchorOn: { backgroundColor: colors.accentFill },
  anchorPressed: { backgroundColor: colors.fill },
  anchorText: { fontSize: 11.5, fontWeight: "800", letterSpacing: -0.2, color: colors.sec },
  anchorTextOn: { color: colors.accentText },
  pressed: { opacity: 0.9, transform: [{ scale: 0.975 }] },
  dimmed: { opacity: 0.55 },
  selectedRing: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    borderRadius: 16,
    borderWidth: 2.5,
    borderColor: colors.accent,
  },
  hairline: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.line,
  },
  tag: {
    position: "absolute",
    top: 9,
    left: 9,
    height: 24,
    paddingHorizontal: 9,
    borderRadius: 999,
    justifyContent: "center",
    backgroundColor: colors.control,
  },
  tagText: { fontSize: 11, fontWeight: "800", letterSpacing: -0.1, color: colors.onImage },
  fav: {
    position: "absolute",
    top: 9,
    right: 9,
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.control,
  },
  favOn: { backgroundColor: colors.danger },
  caption: { position: "absolute", left: 12, right: 12, bottom: 10 },
  title: { fontSize: 14.5, fontWeight: "800", letterSpacing: -0.3, color: colors.onImage },
  region: { marginTop: 3, fontSize: 11.5, color: colors.onDim },
});
