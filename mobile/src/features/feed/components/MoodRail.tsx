import { View, Text, StyleSheet } from "react-native";
import { router } from "expo-router";
import { Rail } from "@/components/Rail";
import { SpotCard } from "@/components/SpotCard";
import { Icon } from "@/components/Icon";
import { prefetchSpot } from "@/features/spots/queries";
import type { MoodRailDto } from "@/lib/api-types";
import { colors } from "@/constants/theme";

export function MoodRail({ rail }: { rail: MoodRailDto }) {
  return (
    <View style={styles.section}>
      <View style={styles.header}>
        <Text style={styles.title}>{rail.title}</Text>
        <View style={styles.more}>
          <Text style={styles.moreText}>더보기</Text>
          <Icon name="chevron-right" size={13} color={colors.ter} strokeWidth={2.4} />
        </View>
      </View>
      <Rail>
        {rail.spots.map((spot) => (
          <SpotCard
            key={spot.contentId}
            spot={spot}
            onPressIn={() => prefetchSpot(spot)}
            onPress={() => router.push(`/spots/${spot.contentId}`)}
          />
        ))}
      </Rail>
    </View>
  );
}

const styles = StyleSheet.create({
  section: { paddingTop: 20, paddingBottom: 20 },
  header: {
    flexDirection: "row",
    alignItems: "baseline",
    justifyContent: "space-between",
    paddingHorizontal: 20,
    paddingBottom: 8,
  },
  title: { fontSize: 17, fontWeight: "800", letterSpacing: -0.3, color: colors.ink },
  more: { flexDirection: "row", alignItems: "center", gap: 1 },
  moreText: { fontSize: 12.5, fontWeight: "600", color: colors.ter },
});
