import { Pressable, View, Text, StyleSheet } from "react-native";
import { RemoteImage } from "@/components/RemoteImage";
import { Icon } from "@/components/Icon";
import { useSaveOptimistic } from "@/features/saved/hooks/use-save-optimistic";
import { distanceReading } from "@/features/travel/lib/distance";
import type { TravelSpot } from "@/features/travel/api";
import { colors, radii, spacing } from "@/constants/theme";

export const ANCHOR_NOTE = "이 장소 기준으로 이어서 물어요";
export const ANCHOR_DETAIL = "자세히";
export const ANCHOR_RELEASE = "기준 해제";

interface Props {
  spot: TravelSpot;
  distanceKm?: number | null;
  onDetail: () => void;
  onRelease: () => void;
  onSaveToggle?: (saved: boolean) => void;
}

export function AnchorPreview({
  spot,
  distanceKm = null,
  onDetail,
  onRelease,
  onSaveToggle,
}: Props) {
  const { saved, toggle } = useSaveOptimistic(spot.contentId);
  const reading = distanceKm === null ? null : distanceReading(distanceKm);
  const sub = [spot.regionLabel, reading ? `${reading.value}${reading.unit}` : null, spot.tag]
    .filter(Boolean)
    .join(" · ");

  return (
    <View style={styles.root} testID="travel-anchor-preview">
      <View style={styles.head}>
        <RemoteImage uri={spot.imageUrl} style={styles.thumb} radius={15} />
        <View style={styles.copy}>
          <Text style={styles.title} numberOfLines={1}>
            {spot.title}
          </Text>
          <Text style={styles.sub} numberOfLines={1}>
            {sub}
          </Text>
          <Text style={styles.note}>{ANCHOR_NOTE}</Text>
        </View>
        <Pressable
          testID={`travel-anchor-save-${spot.contentId}`}
          accessibilityRole="button"
          accessibilityLabel={saved ? "저장 해제" : "저장"}
          accessibilityState={{ selected: saved }}
          style={styles.fav}
          hitSlop={8}
          onPress={async () => {
            const result = await toggle();
            if (result !== null) onSaveToggle?.(result);
          }}
        >
          <Icon
            name={saved ? "heart-fill" : "heart"}
            size={17}
            color={saved ? colors.accent : colors.ink}
            strokeWidth={1.9}
          />
        </Pressable>
      </View>

      <View style={styles.actions}>
        <Pressable
          testID="travel-anchor-release"
          accessibilityRole="button"
          style={({ pressed }) => [styles.action, pressed && styles.pressed]}
          onPress={onRelease}
        >
          <Text style={styles.actionText}>{ANCHOR_RELEASE}</Text>
        </Pressable>
        <Pressable
          testID="travel-anchor-detail"
          accessibilityRole="button"
          style={({ pressed }) => [styles.action, styles.actionPrimary, pressed && styles.pressed]}
          onPress={onDetail}
        >
          <Text style={[styles.actionText, styles.actionTextPrimary]}>{ANCHOR_DETAIL}</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    marginHorizontal: spacing.md,
    marginTop: spacing.sm,
    padding: 12,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.glassBorder,
    backgroundColor: colors.raise,
  },
  head: { flexDirection: "row", alignItems: "center", gap: 13 },
  thumb: { width: 62, height: 62 },
  copy: { flex: 1, minWidth: 0 },
  title: { fontSize: 18, fontWeight: "800", letterSpacing: -0.6, color: colors.ink },
  sub: { marginTop: 4, fontSize: 12.5, color: colors.sec },
  note: { marginTop: 4, fontSize: 11.5, color: colors.accentText },
  fav: {
    width: 34,
    height: 34,
    borderRadius: 17,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.fillStrong,
  },
  actions: { flexDirection: "row", gap: 8, marginTop: 12 },
  action: {
    flex: 1,
    height: 42,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.raiseStrong,
    alignItems: "center",
    justifyContent: "center",
  },
  actionPrimary: { backgroundColor: colors.accent, borderColor: colors.accent },
  pressed: { opacity: 0.7 },
  actionText: { fontSize: 13.5, fontWeight: "700", letterSpacing: -0.2, color: colors.ink },
  actionTextPrimary: { color: colors.onImage },
});
