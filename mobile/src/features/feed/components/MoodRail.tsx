import { View, Text, StyleSheet } from "react-native";
import { router } from "expo-router";
import { Rail } from "@/components/Rail";
import { SpotCard } from "@/components/SpotCard";
import { prefetchSpot } from "@/features/spots/queries";
import type { MoodRailDto } from "@/lib/api-types";
import { colors, spacing } from "@/constants/theme";

export function MoodRail({ rail }: { rail: MoodRailDto }) {
  return (
    <View style={styles.section}>
      <View style={styles.header}>
        <Text style={styles.title}>{rail.title}</Text>
        {rail.subtitle ? <Text style={styles.subtitle}>{rail.subtitle}</Text> : null}
      </View>
      <Rail>
        {rail.spots.map((spot) => (
          <SpotCard
            key={spot.contentId}
            spot={spot}
            onPressIn={() => prefetchSpot(spot.contentId)}
            onPress={() => router.push(`/spots/${spot.contentId}`)}
          />
        ))}
      </Rail>
    </View>
  );
}

const styles = StyleSheet.create({
  section: { marginTop: spacing.xxl },
  header: { paddingHorizontal: spacing.lg, marginBottom: spacing.md },
  title: { fontSize: 22, fontWeight: "800", letterSpacing: -0.3, color: colors.ink },
  subtitle: { marginTop: 4, fontSize: 14, color: colors.ter },
});
