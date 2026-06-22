import { ScrollView, View, Text, StyleSheet } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useHomeFeed } from "@/features/feed/queries";
import { HeroCarousel } from "@/features/feed/components/HeroCarousel";
import { MoodRail } from "@/features/feed/components/MoodRail";
import { Skeleton } from "@/components/Skeleton";
import { PrimaryButton } from "@/components/PrimaryButton";
import { colors, spacing } from "@/constants/theme";

export default function HomeScreen() {
  const { data, isLoading, isError, refetch } = useHomeFeed();

  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      <View style={styles.bar}>
        <Text style={styles.wordmark}>PicTrip</Text>
      </View>

      {isLoading ? (
        <View style={styles.loading}>
          <Skeleton height={360} radius={20} />
          <Skeleton height={20} width="40%" style={{ marginTop: spacing.xxl }} />
          <Skeleton height={140} style={{ marginTop: spacing.md }} />
        </View>
      ) : isError || !data ? (
        <View style={styles.error}>
          <Text style={styles.errorText}>피드를 불러오지 못했어요.</Text>
          <PrimaryButton label="다시 시도" onPress={() => refetch()} />
        </View>
      ) : (
        <ScrollView
          showsVerticalScrollIndicator={false}
          contentContainerStyle={{ paddingBottom: spacing.xxl }}
        >
          <View style={{ paddingTop: spacing.md }}>
            <HeroCarousel heroes={data.heroes} />
          </View>
          {data.rails.map((rail) => (
            <MoodRail key={rail.id} rail={rail} />
          ))}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  bar: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  wordmark: { fontSize: 20, fontWeight: "800", letterSpacing: -0.5, color: colors.ink },
  loading: { padding: spacing.lg },
  error: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.md,
    padding: spacing.xl,
  },
  errorText: { fontSize: 15, color: colors.sec },
});
