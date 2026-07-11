import { View, Text, StyleSheet } from "react-native";
import { router } from "expo-router";
import { Rail } from "@/components/Rail";
import { SpotCard } from "@/components/SpotCard";
import { useNearby, prefetchSpot } from "@/features/spots/queries";
import { colors } from "@/constants/theme";

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
      <Text style={styles.h2}>주변 추천</Text>
      <Rail gap={10}>
        {data.map((spot) => (
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
  section: { paddingTop: 22, paddingBottom: 4 },
  h2: {
    fontSize: 19,
    fontWeight: "800",
    letterSpacing: -0.4,
    color: colors.ink,
    paddingHorizontal: 20,
    marginBottom: 12,
  },
});
