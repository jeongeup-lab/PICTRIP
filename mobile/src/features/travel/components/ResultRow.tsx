import { Pressable, View, Text, StyleSheet } from "react-native";
import { router } from "expo-router";
import { RemoteImage } from "@/components/RemoteImage";
import { Icon } from "@/components/Icon";
import { useSaveOptimistic } from "@/features/saved/hooks/use-save-optimistic";
import { prefetchSpot } from "@/features/spots/queries";
import { distanceReading } from "@/features/travel/lib/distance";
import type { TravelSpot } from "@/features/travel/api";
import { colors, radii, spacing } from "@/constants/theme";

export const DETAIL_ACTION = "detail";

export type RowTone = "neutral" | "result";

interface Props {
  spot: TravelSpot;
  index: number;
  tone?: RowTone;
  selected?: boolean;
  dimmed?: boolean;
  distanceKm?: number | null;
  first?: boolean;
  onPress?: () => void;
  onDetail?: () => void;
  onSaveToggle?: (saved: boolean) => void;
}

export function ResultRow({
  spot,
  index,
  tone = "neutral",
  selected = false,
  dimmed = false,
  distanceKm = null,
  first = false,
  onPress,
  onDetail,
  onSaveToggle,
}: Props) {
  const { saved, toggle } = useSaveOptimistic(spot.contentId);
  const reading = distanceKm === null ? null : distanceReading(distanceKm);
  const badgeStyle = selected
    ? styles.badgeSelected
    : tone === "result"
      ? styles.badgeResult
      : null;

  return (
    <View style={[styles.row, !first && styles.divided, dimmed && styles.dimmed]}>
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
        <View style={[styles.badge, badgeStyle]}>
          <Text style={[styles.badgeText, selected && styles.badgeTextOn]}>{index + 1}</Text>
        </View>

        <RemoteImage uri={spot.imageUrl} style={styles.thumb} radius={11} />

        <View style={styles.copy}>
          <Text style={styles.title} numberOfLines={1}>
            {spot.title}
          </Text>
          <Text style={styles.sub} numberOfLines={1}>
            {spot.regionLabel}
            {spot.tag ? " · " : ""}
            {spot.tag ? <Text style={styles.tag}>{spot.tag}</Text> : null}
          </Text>
        </View>

        {reading ? (
          <View style={styles.reading}>
            <Text style={styles.readingValue}>{reading.value}</Text>
            <Text style={styles.readingUnit}>{reading.unit}</Text>
          </View>
        ) : null}
      </Pressable>

      <Pressable
        testID={`travel-spot-save-${spot.contentId}`}
        accessibilityRole="button"
        accessibilityLabel={saved ? "저장 해제" : "저장"}
        accessibilityState={{ selected: saved }}
        style={({ pressed }) => [styles.fav, pressed && styles.pressed]}
        hitSlop={8}
        onPress={async () => {
          const result = await toggle();
          if (result !== null) onSaveToggle?.(result);
        }}
      >
        <Icon
          name={saved ? "heart-fill" : "heart"}
          size={16}
          color={saved ? colors.accent : colors.ter}
          strokeWidth={1.9}
        />
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", paddingRight: spacing.md },
  divided: { borderTopWidth: 1, borderTopColor: colors.line },
  dimmed: { opacity: 0.5 },
  tapArea: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingVertical: 11,
    paddingLeft: spacing.lg,
  },
  pressed: { opacity: 0.6 },
  badge: {
    width: 24,
    height: 24,
    borderRadius: radii.md,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.fillStrong,
  },
  badgeResult: { backgroundColor: colors.info },
  badgeSelected: { backgroundColor: colors.accent },
  badgeText: { fontSize: 12, fontWeight: "800", color: colors.ink },
  badgeTextOn: { color: colors.onImage },
  thumb: { width: 48, height: 48 },
  copy: { flex: 1, minWidth: 0 },
  title: { fontSize: 15, fontWeight: "700", letterSpacing: -0.3, color: colors.ink },
  sub: { marginTop: 3, fontSize: 12.5, color: colors.sec },
  tag: { color: colors.positive, fontWeight: "600" },
  reading: { alignItems: "flex-end" },
  readingValue: { fontSize: 14, fontWeight: "700", color: colors.ink },
  readingUnit: { marginTop: 3, fontSize: 11, color: colors.ter },
  fav: { width: 30, height: 30, alignItems: "center", justifyContent: "center" },
});
