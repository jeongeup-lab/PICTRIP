import { Pressable, View, Text, StyleSheet } from "react-native";
import { RemoteImage } from "@/components/RemoteImage";
import { Icon } from "@/components/Icon";
import type { ScheduleSlot } from "@/features/plan/api";
import { TIME_OF_DAY_LABEL, placeName, shortRegion } from "@/features/plan/lib/plan-format";
import { colors, radii, shadows, spacing } from "@/constants/theme";

interface Props {
  slot: ScheduleSlot;
  first: boolean;
  onPress: () => void;
}

export function TravelGap({ minutes }: { minutes: number }) {
  return (
    <View style={styles.travel}>
      <Icon name="arrow-down" size={12} color={colors.ter} strokeWidth={1.8} />
      <Text style={styles.travelText}>이동 약 {minutes}분</Text>
    </View>
  );
}

export function SlotRow({ slot, first, onPress }: Props) {
  const spot = slot.place.spot;
  const meta = [spot?.category, shortRegion(spot?.address)].filter(Boolean).join(" · ");

  return (
    <Pressable
      testID={`slot-${placeName(slot.place)}`}
      style={({ pressed }) => [styles.slot, pressed && styles.pressed]}
      onPress={onPress}
    >
      <View style={[styles.dot, first && styles.dotFirst]} />
      <Text style={styles.tod}>{TIME_OF_DAY_LABEL[slot.timeOfDay]}</Text>
      <View style={styles.card}>
        <RemoteImage uri={spot?.imageUrl ?? null} style={styles.image} radius={radii.md} />
        <View style={styles.body}>
          <Text style={styles.title} numberOfLines={1}>
            {placeName(slot.place)}
          </Text>
          {meta ? (
            <Text style={styles.meta} numberOfLines={1}>
              {meta}
            </Text>
          ) : null}
        </View>
        <Icon name="chevron-right" size={18} color={colors.ter} />
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  slot: { paddingVertical: 8 },
  pressed: { opacity: 0.7 },
  dot: {
    position: "absolute",
    left: -25.5,
    top: 38,
    width: 11,
    height: 11,
    borderRadius: 5.5,
    borderWidth: 2,
    borderColor: colors.ink,
    backgroundColor: colors.inset,
  },
  dotFirst: { backgroundColor: colors.ink },
  tod: { fontSize: 11, fontWeight: "700", color: colors.ter, marginBottom: 6 },
  card: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    backgroundColor: colors.bg,
    borderRadius: radii.lg,
    padding: 11,
    ...shadows.card,
  },
  image: { width: 62, height: 62 },
  body: { flex: 1, gap: 3 },
  title: { fontSize: 15, fontWeight: "700", letterSpacing: -0.2, color: colors.ink },
  meta: { fontSize: 12.5, color: colors.ter },
  travel: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    paddingVertical: 3,
    paddingLeft: spacing.xs,
  },
  travelText: { fontSize: 11.5, fontWeight: "600", color: colors.ter },
});
