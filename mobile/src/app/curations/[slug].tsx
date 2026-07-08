import { ScrollView, View, Text, Pressable, useWindowDimensions, StyleSheet } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useLocalSearchParams, router } from "expo-router";
import { useCuration } from "@/features/curation/queries";
import { shareCuration } from "@/features/curation/share";
import { CurationIntro } from "@/features/curation/components/CurationIntro";
import { prefetchSpot } from "@/features/spots/queries";
import { AppBar } from "@/components/AppBar";
import { Icon } from "@/components/Icon";
import { PrimaryButton } from "@/components/PrimaryButton";
import { RemoteImage } from "@/components/RemoteImage";
import { SpotCard } from "@/components/SpotCard";
import { Skeleton } from "@/components/Skeleton";
import { AppError } from "@/lib/app-error";
import { colors, spacing, radii } from "@/constants/theme";

export default function CurationScreen() {
  const { slug } = useLocalSearchParams<{ slug: string }>();
  const { data, isLoading, isError, error, refetch } = useCuration(slug);
  const { width } = useWindowDimensions();
  const cardWidth = (width - spacing.lg * 2 - spacing.md) / 2;

  // 404 (unpublished/deleted) vs everything else — branch on err.code, not message.
  const notFound = isError && error instanceof AppError && error.code === "RESOURCE_NOT_FOUND";

  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      <AppBar
        onBack={() => router.back()}
        right={
          data ? (
            <Pressable
              testID="curation-share"
              accessibilityRole="button"
              accessibilityLabel="공유"
              hitSlop={8}
              onPress={() => void shareCuration(data.title, data.slug)}
              style={styles.shareBtn}
            >
              <Icon name="share" size={20} />
            </Pressable>
          ) : undefined
        }
      />
      {isError ? (
        <View style={styles.state}>
          <Text style={styles.stateText}>
            {notFound ? "큐레이션을 찾을 수 없어요" : "큐레이션을 불러오지 못했어요."}
          </Text>
          {notFound ? (
            <PrimaryButton label="뒤로가기" onPress={() => router.back()} />
          ) : (
            <PrimaryButton label="다시 시도" onPress={() => void refetch()} />
          )}
        </View>
      ) : (
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
              {data.intro ? <CurationIntro intro={data.intro} /> : null}
              {data.spots.length === 0 ? (
                <View style={styles.emptyGrid}>
                  <Text style={styles.emptyGridText}>곧 새로운 스팟을 준비할게요</Text>
                </View>
              ) : (
                <View style={styles.grid}>
                  {data.spots.map((spot) => (
                    <SpotCard
                      key={spot.contentId}
                      spot={spot}
                      width={cardWidth}
                      onPressIn={() => prefetchSpot(spot)}
                      onPress={() => router.push(`/spots/${spot.contentId}`)}
                    />
                  ))}
                </View>
              )}
            </>
          )}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  shareBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.inset,
  },
  state: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.md,
    padding: spacing.xl,
  },
  stateText: { fontSize: 15, color: colors.sec },
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
    textAlign: "center",
    color: colors.ink,
    paddingHorizontal: spacing.lg,
    marginTop: spacing.lg,
  },
  emptyGrid: {
    marginHorizontal: spacing.lg,
    marginTop: spacing.xl,
    paddingVertical: spacing.xxl,
    borderRadius: radii.lg,
    backgroundColor: colors.inset,
    alignItems: "center",
  },
  emptyGridText: { fontSize: 14, color: colors.ter },
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.md,
    paddingHorizontal: spacing.lg,
    marginTop: spacing.xl,
  },
});
