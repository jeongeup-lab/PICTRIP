import { View, Text, Pressable, ScrollView, StyleSheet } from "react-native";
import { router } from "expo-router";
import { RemoteImage } from "@/components/RemoteImage";
import { useNearby } from "@/features/spots/queries";
import type { NearbySpot } from "@/lib/api-types";
import { colors } from "@/constants/theme";

function NearbyCard({ spot }: { spot: NearbySpot }) {
  return (
    <Pressable style={styles.card} onPress={() => router.push(`/spots/${spot.contentId}`)}>
      <RemoteImage uri={spot.firstImageUrl} radius={13} style={styles.photo} />
      <Text style={styles.name} numberOfLines={1}>
        {spot.title}
      </Text>
      {spot.category ? (
        <Text style={styles.cat} numberOfLines={1}>
          {spot.category}
        </Text>
      ) : null}
    </Pressable>
  );
}

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
      <Text style={styles.h3}>주변 둘러보기</Text>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.rail}
      >
        {data.map((spot) => (
          <NearbyCard key={spot.contentId} spot={spot} />
        ))}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  section: { paddingTop: 22, marginTop: 24 },
  h3: {
    fontSize: 17,
    fontWeight: "700",
    letterSpacing: -0.17,
    color: colors.ink,
    paddingHorizontal: 20,
    marginBottom: 12,
  },
  rail: { gap: 12, paddingHorizontal: 20, paddingBottom: 4 },
  card: { width: 150 },
  photo: { width: 150, height: 112 },
  name: { fontSize: 14, fontWeight: "600", color: colors.ink, marginTop: 9 },
  cat: { fontSize: 13, fontWeight: "500", color: colors.ter, marginTop: 2 },
});
