import { View, Text, StyleSheet } from "react-native";
import { router } from "expo-router";
import { Rail } from "@/components/Rail";
import { SpotCard } from "@/components/SpotCard";
import { useNearby } from "@/features/spots/queries";
import { colors, spacing } from "@/constants/theme";

export function NearbyRail({
  lat,
  lng,
  excludeId,
}: {
  lat: number | null;
  lng: number | null;
  excludeId: string;
}) {
  const { data } = useNearby(lat, lng, excludeId);
  if (!data || data.length === 0) return null;
  return (
    <View style={styles.section}>
      <Text style={styles.title}>주변 장소</Text>
      <Rail>
        {data.map((spot) => (
          <SpotCard
            key={spot.contentId}
            spot={spot}
            onPress={() => router.push(`/spots/${spot.contentId}`)}
          />
        ))}
      </Rail>
    </View>
  );
}

const styles = StyleSheet.create({
  section: { marginTop: spacing.xxl },
  title: {
    fontSize: 22,
    fontWeight: "800",
    letterSpacing: -0.3,
    color: colors.ink,
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
});
