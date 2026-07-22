import { Pressable, View, Text, StyleSheet } from "react-native";
import { RemoteImage } from "@/components/RemoteImage";
import { shortDurationLabel } from "@/features/plan/lib/plan-format";
import type { RecentPlan } from "@/features/plan/lib/recent-plans";
import { colors, radii } from "@/constants/theme";

interface Props {
  plan: RecentPlan;
  onPress: () => void;
}

export function RecentPlanCard({ plan, onPress }: Props) {
  return (
    <Pressable
      testID={`recent-plan-${plan.id}`}
      style={({ pressed }) => [styles.card, pressed && styles.pressed]}
      onPress={onPress}
    >
      {plan.thumb ? (
        <>
          <RemoteImage uri={plan.thumb} style={StyleSheet.absoluteFill} />
          <View style={styles.scrim} />
        </>
      ) : null}
      <View style={styles.badge}>
        <Text style={styles.badgeText}>{shortDurationLabel(plan.days)}</Text>
      </View>
      <View style={styles.cap}>
        <Text style={[styles.title, !plan.thumb && styles.titleDark]} numberOfLines={1}>
          {plan.title}
        </Text>
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
  pressed: { opacity: 0.85 },
  scrim: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: "rgba(16,14,18,0.34)",
  },
  badge: {
    position: "absolute",
    top: 8,
    right: 8,
    height: 24,
    paddingHorizontal: 9,
    borderRadius: 12,
    backgroundColor: colors.control,
    alignItems: "center",
    justifyContent: "center",
  },
  badgeText: { fontSize: 10.5, fontWeight: "700", color: colors.onImage },
  cap: { position: "absolute", left: 12, right: 12, bottom: 11 },
  title: { fontSize: 13.5, fontWeight: "700", letterSpacing: -0.2, color: colors.onImage },
  titleDark: { color: colors.ink },
});
