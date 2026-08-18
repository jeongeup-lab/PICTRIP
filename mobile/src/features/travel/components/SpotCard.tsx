import { Pressable, View, Text, StyleSheet } from "react-native";
import { RemoteImage } from "@/components/RemoteImage";
import { Icon, type IconName } from "@/components/Icon";
import { useSaveOptimistic } from "@/features/saved/hooks/use-save-optimistic";
import { prefetchSpot } from "@/features/spots/queries";
import { distanceLabel } from "@/features/travel/lib/distance";
import { metricOf, type Metric } from "@/features/travel/lib/metric";
import type { TravelSpot } from "@/features/travel/api";
import { colors, radii } from "@/constants/theme";

export const CARD_WIDTH = 296;
export const CARD_HEIGHT = 112;
export const CARD_GAP = 10;
export const CARD_STRIDE = CARD_WIDTH + CARD_GAP;

export const DETAIL_LABEL = "상세보기";
export const EXTERNAL_LABEL = "카카오맵";

const KIND_ICONS: Record<string, IconName> = {
  cafe: "tag",
  food: "tag",
  attraction: "image",
};

function metersLabel(meters: number | null | undefined): string | null {
  if (typeof meters !== "number" || meters <= 0) return null;
  return meters >= 1000 ? `${(meters / 1000).toFixed(1)}km` : `${meters}m`;
}

interface Props {
  spot: TravelSpot;
  index: number;
  tagBasis: string | null;
  distanceKm: number | null;
  focused: boolean;
  onDetail: () => void;
  onSaveToggle: (saved: boolean) => void;
  onMetricPress: (tooltip: string) => void;
}

function MetricChip({ metric, onPress }: { metric: Metric; onPress: (tooltip: string) => void }) {
  const face = (
    <>
      <Icon name={metric.icon} size={13} color={colors.ter} strokeWidth={1.9} />
      <Text style={styles.metricText}>{metric.label}</Text>
    </>
  );

  if (!metric.tooltip) {
    return (
      <View testID="travel-metric" accessibilityLabel={metric.label} style={styles.metric}>
        {face}
      </View>
    );
  }

  return (
    <Pressable
      testID="travel-metric"
      accessibilityRole="button"
      accessibilityLabel={`${metric.label}, ${metric.tooltip}`}
      style={styles.metric}
      hitSlop={6}
      onPress={() => onPress(metric.tooltip)}
    >
      {face}
    </Pressable>
  );
}

export function SpotCard({
  spot,
  index,
  tagBasis,
  distanceKm,
  focused,
  onDetail,
  onSaveToggle,
  onMetricPress,
}: Props) {
  const { saved, toggle } = useSaveOptimistic(spot.contentId);
  const metric = metricOf(spot.tag, tagBasis);
  const distance = distanceLabel(spot.tag, distanceKm) ?? metersLabel(spot.distanceM);
  const external = spot.saveable === false;

  return (
    <View style={styles.card}>
      <Pressable
        testID={`travel-card-${spot.contentId}`}
        accessibilityRole="button"
        accessibilityLabel={`${spot.title} ${external ? EXTERNAL_LABEL : DETAIL_LABEL}`}
        style={({ pressed }) => [styles.tap, pressed && styles.pressed]}
        onPressIn={() => prefetchSpot(spot)}
        onPress={onDetail}
      >
        {external ? (
          <View style={[styles.thumb, styles.thumbBlank]}>
            <Icon
              name={KIND_ICONS[spot.categoryGroup ?? ""] ?? "map-pin"}
              size={22}
              color={colors.ter}
              strokeWidth={1.6}
            />
          </View>
        ) : (
          <RemoteImage
            uri={spot.imageUrl ?? spot.fallbackImageUrl ?? null}
            style={styles.thumb}
            radius={12}
          />
        )}

        <View style={styles.copy}>
          <View style={styles.head}>
            <View testID="travel-card-badge" style={[styles.badge, focused && styles.badgeFocused]}>
              <Text style={[styles.badgeText, focused && styles.badgeTextFocused]}>
                {index + 1}
              </Text>
            </View>
            <Text style={styles.title} numberOfLines={1}>
              {spot.title}
            </Text>
          </View>

          <Text style={styles.region} numberOfLines={1}>
            {spot.regionLabel}
            {distance ? " · " : ""}
            {distance ? <Text style={styles.distance}>{distance}</Text> : null}
          </Text>

          <View style={styles.row}>
            <View style={styles.chips}>
              {metric ? <MetricChip metric={metric} onPress={onMetricPress} /> : null}
              {(spot.chips ?? [])
                .filter((chip) => chip !== spot.tag)
                .slice(0, 2)
                .map((chip) => (
                  <View key={chip} style={styles.chip}>
                    <Text style={styles.chipText}>{chip}</Text>
                  </View>
                ))}
            </View>

            <Pressable
              testID="travel-card-detail"
              accessibilityRole="button"
              accessibilityLabel={`${spot.title} ${external ? EXTERNAL_LABEL : DETAIL_LABEL}`}
              style={({ pressed }) => [styles.detail, pressed && styles.pressed]}
              hitSlop={6}
              onPress={onDetail}
            >
              <Text style={styles.detailText}>{external ? EXTERNAL_LABEL : DETAIL_LABEL}</Text>
              <Icon name="chevron-right" size={12} color={colors.ter} strokeWidth={2} />
            </Pressable>
          </View>
        </View>
      </Pressable>

      {external ? null : (
        <Pressable
          testID={`travel-card-save-${spot.contentId}`}
          accessibilityRole="button"
          accessibilityLabel={saved ? "저장 해제" : "저장"}
          accessibilityState={{ selected: saved }}
          style={styles.fav}
          hitSlop={8}
          onPress={async () => {
            const result = await toggle();
            if (result !== null) onSaveToggle(result);
          }}
        >
          <Icon
            name={saved ? "bookmark-fill" : "bookmark"}
            size={17}
            color={saved ? colors.accent : colors.ter}
            strokeWidth={1.9}
          />
        </Pressable>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  chips: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    flexShrink: 1,
  },
  chip: {
    paddingVertical: 3,
    paddingHorizontal: 8,
    borderRadius: 7,
    backgroundColor: colors.fillStrong,
  },
  chipText: {
    fontSize: 11.5,
    fontWeight: "500",
    color: colors.sec,
  },
  card: {
    width: CARD_WIDTH,
    height: CARD_HEIGHT,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: colors.glassBorder,
    backgroundColor: colors.glassFill,
  },
  tap: { flex: 1, flexDirection: "row", gap: 12, padding: 10 },
  pressed: { opacity: 0.7 },
  thumb: { width: 92, height: 92 },
  thumbBlank: {
    borderRadius: 12,
    backgroundColor: colors.skeleton,
    alignItems: "center",
    justifyContent: "center",
  },
  copy: { flex: 1, minWidth: 0, justifyContent: "center" },
  head: { flexDirection: "row", alignItems: "center", gap: 7, paddingRight: 26 },
  badge: {
    width: 20,
    height: 20,
    borderRadius: 10,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.ink,
  },
  badgeFocused: { backgroundColor: colors.accent },
  badgeText: { fontSize: 11, fontWeight: "800", color: colors.bg },
  badgeTextFocused: { color: colors.onImage },
  title: {
    flex: 1,
    minWidth: 0,
    fontSize: 15,
    fontWeight: "700",
    letterSpacing: -0.35,
    color: colors.ink,
  },
  region: { marginTop: 3, fontSize: 12.5, letterSpacing: -0.2, color: colors.sec },
  distance: { fontWeight: "700", color: colors.ink },
  row: { flexDirection: "row", alignItems: "center", gap: 6, marginTop: 7 },
  metric: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    height: 22,
    paddingHorizontal: 8,
    borderRadius: 7,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.fill,
  },
  metricText: { fontSize: 11.5, fontWeight: "700", letterSpacing: -0.2, color: colors.sec },
  detail: {
    flexDirection: "row",
    alignItems: "center",
    gap: 2,
    height: 24,
    marginLeft: "auto",
    paddingLeft: 10,
    paddingRight: 8,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.line,
  },
  detailText: { fontSize: 11.5, fontWeight: "700", letterSpacing: -0.2, color: colors.sec },
  fav: {
    position: "absolute",
    top: 8,
    right: 8,
    width: 26,
    height: 26,
    alignItems: "center",
    justifyContent: "center",
  },
});
