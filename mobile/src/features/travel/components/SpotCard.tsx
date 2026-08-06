import { Pressable, View, Text, StyleSheet, type StyleProp, type ViewStyle } from "react-native";
import Svg, { Defs, LinearGradient, Stop, Rect } from "react-native-svg";
import { router } from "expo-router";
import { RemoteImage } from "@/components/RemoteImage";
import { Icon } from "@/components/Icon";
import { useSaveOptimistic } from "@/features/saved/hooks/use-save-optimistic";
import { prefetchSpot } from "@/features/spots/queries";
import type { TravelSpot } from "@/features/travel/api";
import { colors } from "@/constants/theme";

export const RAIL_CARD_WIDTH = 168;
export const MEDIA_HEIGHT = 150;
export const RAIL_CARD_HEIGHT = MEDIA_HEIGHT;

export const DETAIL_ACTION = "detail";

interface Props {
  spot: TravelSpot;
  style?: StyleProp<ViewStyle>;
  onSaveToggle?: (saved: boolean) => void;
  onPress?: () => void;
  onDetail?: () => void;
  selected?: boolean;
  dimmed?: boolean;
}

export function SpotCard({
  spot,
  style,
  onSaveToggle,
  onPress,
  onDetail,
  selected,
  dimmed,
}: Props) {
  const { saved, toggle } = useSaveOptimistic(spot.contentId);

  return (
    <View style={[styles.card, style, dimmed && styles.dimmed]}>
      <Pressable
        testID={`travel-spot-${spot.contentId}`}
        style={({ pressed }) => [styles.tapArea, pressed && styles.pressed]}
        onPressIn={() => prefetchSpot(spot)}
        onPress={onPress ?? (() => router.push(`/spots/${spot.contentId}`))}
        accessibilityRole="button"
        accessibilityHint={onDetail ? "이 장소 기준으로 이어서 물어요" : undefined}
        accessibilityActions={onDetail ? [{ name: DETAIL_ACTION, label: "상세 보기" }] : undefined}
        onAccessibilityAction={
          onDetail
            ? (event) => {
                if (event.nativeEvent.actionName === DETAIL_ACTION) onDetail();
              }
            : undefined
        }
      >
        <View style={styles.media}>
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

          <View style={styles.caption}>
            <Text style={styles.title} numberOfLines={1}>
              {spot.title}
            </Text>
            <Text style={styles.region} numberOfLines={1}>
              {spot.regionLabel}
            </Text>
          </View>
        </View>
      </Pressable>

      <Pressable
        testID={`travel-spot-save-${spot.contentId}`}
        accessibilityRole="button"
        accessibilityLabel={saved ? "저장 해제" : "저장"}
        accessibilityState={{ selected: saved }}
        style={[styles.fav, saved && styles.favOn]}
        hitSlop={8}
        onPress={async () => {
          const result = await toggle();
          if (result !== null) onSaveToggle?.(result);
        }}
      >
        <Icon
          name={saved ? "heart-fill" : "heart"}
          size={14}
          color={colors.onImage}
          strokeWidth={1.9}
        />
      </Pressable>

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
  tapArea: { height: MEDIA_HEIGHT },
  media: { height: MEDIA_HEIGHT },
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
