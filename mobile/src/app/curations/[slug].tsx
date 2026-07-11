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
  const cardWidth = (width - GUTTER * 2 - spacing.md) / 2;

  // 404 (unpublished/deleted) vs everything else — branch on err.code, not message.
  const notFound = isError && error instanceof AppError && error.code === "RESOURCE_NOT_FOUND";

  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      <AppBar
        bordered
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
            <View style={styles.loading}>
              <Skeleton height={16} width="30%" />
              <Skeleton height={30} width="70%" />
              <Skeleton height={(width - GUTTER * 2) * (5 / 4)} radius={radii.lg} />
            </View>
          ) : (
            <>
              <View style={styles.titleBlock}>
                <Text style={styles.eyebrow}>CURATION</Text>
                <Text style={styles.title}>{data.title}</Text>
                <Text style={styles.meta}>스팟 {data.spots.length}곳</Text>
              </View>
              <View style={styles.coverWrap}>
                <RemoteImage
                  uri={data.coverUrl}
                  radius={radii.lg}
                  style={{ width: "100%", aspectRatio: 4 / 5 }}
                />
              </View>
              {data.lead ? <Text style={styles.lead}>{data.lead}</Text> : null}
              {data.intro ? <CurationIntro intro={data.intro} /> : null}
              <View style={styles.band} />
              <Text style={styles.sectionHeader}>포함된 스팟</Text>
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

const GUTTER = 16;

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  shareBtn: {
    width: 40,
    height: 40,
    alignItems: "center",
    justifyContent: "center",
  },
  state: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.md,
    padding: spacing.xl,
  },
  stateText: { fontSize: 15, color: colors.sec },
  loading: { padding: GUTTER, gap: spacing.md },
  titleBlock: {
    paddingHorizontal: GUTTER,
    marginTop: spacing.md,
    marginBottom: spacing.lg,
    gap: spacing.xs,
  },
  eyebrow: {
    fontSize: 11,
    fontWeight: "800",
    letterSpacing: 1.5,
    color: colors.accentText,
  },
  title: {
    fontSize: 24,
    fontWeight: "800",
    letterSpacing: -0.55,
    color: colors.ink,
  },
  meta: { fontSize: 13, color: colors.ter },
  coverWrap: { marginHorizontal: GUTTER },
  lead: {
    fontSize: 15,
    fontWeight: "700",
    color: colors.ink,
    paddingHorizontal: GUTTER,
    marginTop: spacing.lg,
  },
  band: {
    height: 8,
    marginTop: spacing.xl,
    backgroundColor: colors.inset,
    borderTopWidth: 1,
    borderBottomWidth: 1,
    borderColor: colors.fill,
  },
  sectionHeader: {
    fontSize: 17,
    fontWeight: "800",
    letterSpacing: -0.3,
    color: colors.ink,
    paddingHorizontal: GUTTER,
    marginTop: spacing.xl,
  },
  emptyGrid: {
    marginHorizontal: GUTTER,
    marginTop: spacing.lg,
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
    paddingHorizontal: GUTTER,
    marginTop: spacing.lg,
  },
});
