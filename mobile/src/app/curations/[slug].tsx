import { ScrollView, View, Text, useWindowDimensions, StyleSheet } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useLocalSearchParams, router } from "expo-router";
import { useCuration } from "@/features/curation/queries";
import { AppBar } from "@/components/AppBar";
import { RemoteImage } from "@/components/RemoteImage";
import { SpotCard } from "@/components/SpotCard";
import { Skeleton } from "@/components/Skeleton";
import { colors, spacing, radii } from "@/constants/theme";

export default function CurationScreen() {
  const { slug } = useLocalSearchParams<{ slug: string }>();
  const { data, isLoading } = useCuration(slug);
  const { width } = useWindowDimensions();
  const cardWidth = (width - spacing.lg * 2 - spacing.md) / 2;

  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      <AppBar onBack={() => router.back()} />
      <ScrollView contentContainerStyle={{ paddingBottom: spacing.xxl }}>
        {isLoading || !data ? (
          <View style={{ padding: spacing.lg, gap: spacing.md }}>
            <Skeleton height={32} width="60%" />
            <Skeleton height={width * 1.0} radius={radii.lg} />
          </View>
        ) : (
          <>
            <Text style={styles.title}>{data.title}</Text>
            <View style={styles.coverWrap}>
              <RemoteImage
                uri={data.coverUrl}
                radius={radii.lg}
                style={{ width: "100%", aspectRatio: 4 / 5 }}
              />
            </View>
            {data.lead ? <Text style={styles.lead}>{data.lead}</Text> : null}
            {data.intro ? <Text style={styles.intro}>{data.intro}</Text> : null}
            <View style={styles.grid}>
              {data.spots.map((spot) => (
                <SpotCard
                  key={spot.contentId}
                  spot={spot}
                  width={cardWidth}
                  onPress={() => router.push(`/spots/${spot.contentId}`)}
                />
              ))}
            </View>
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  title: {
    textAlign: "center",
    fontSize: 25,
    fontWeight: "800",
    letterSpacing: -0.5,
    color: colors.ink,
    paddingHorizontal: spacing.lg,
    marginVertical: spacing.md,
  },
  coverWrap: { paddingHorizontal: spacing.lg },
  lead: {
    fontSize: 16,
    fontWeight: "700",
    color: colors.ink,
    paddingHorizontal: spacing.lg,
    marginTop: spacing.lg,
  },
  intro: {
    fontSize: 15,
    color: colors.sec,
    lineHeight: 23,
    paddingHorizontal: spacing.lg,
    marginTop: spacing.sm,
  },
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.md,
    paddingHorizontal: spacing.lg,
    marginTop: spacing.xl,
  },
});
