import { useCallback, useMemo, useRef, useState } from "react";
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";
import { router, useScrollToTop } from "expo-router";
import { AppBar } from "@/components/AppBar";
import { Icon } from "@/components/Icon";
import { ChannelChips } from "@/features/channels/components/ChannelChips";
import { AiSection } from "@/features/home/components/AiSection";
import {
  CurationSection,
  EditorialRail,
  EditorialRailSkeleton,
} from "@/features/home/components/CurationSection";
import { RankList } from "@/features/home/components/RankList";
import { useHomeLocation } from "@/features/home/hooks/use-home-location";
import { formatBaseDate } from "@/features/home/lib/base-date";
import { scopeTitle, todayLine } from "@/features/home/lib/today-line";
import {
  useCuration,
  useNearby,
  useRecommendations,
  useRegionLabel,
  useTrending,
} from "@/features/home/queries";
import type { HomeSpotCard } from "@/features/home/api";
import { useAuthStore } from "@/features/auth/stores/auth-store";
import { prefetchSpot } from "@/features/spots/queries";
import { queryClient } from "@/lib/query-client";
import { colors, spacing } from "@/constants/theme";

export const RANK_LIMIT = 10;
const RANK_KICKER = "NOW TRENDING";
const SECTION_GAP = 40;
export const LOCATION_CTA = "위치를 켜면 지금 주변 인기 장소를 보여드려요";

type HomeScope = "nearby" | "national";

export default function HomeScreen() {
  const listRef = useRef<ScrollView>(null);
  useScrollToTop(listRef);

  const [scope, setScope] = useState<HomeScope>("nearby");
  const { coords, status, request } = useHomeLocation();
  const displayName = useAuthStore((s) => s.user?.displayName ?? null);

  const region = useRegionLabel(coords);
  const nearby = useNearby(coords);
  const national = useTrending();
  const curation = useCuration();
  const recommendations = useRecommendations(coords);

  const locationDenied = status === "denied" || status === "undetermined";
  const nearbyIsEmpty =
    !nearby.isLoading && !nearby.isError && (nearby.data?.items.length ?? 0) === 0;
  const showNational = scope === "national" || locationDenied || (!!coords && nearbyIsEmpty);
  const active = showNational ? national : nearby;
  const waitingForFix = !showNational && !coords;
  const cards = useMemo(() => active.data?.items ?? [], [active.data]);
  const shown = cards.slice(0, RANK_LIMIT);
  const regionLabel = region.data?.label ?? null;
  const effectiveScope: HomeScope = showNational ? "national" : "nearby";

  const openSpot = useCallback(
    (contentId: string) => {
      const card = findCard(contentId, cards, curation.data?.items);
      if (card) {
        prefetchSpot({
          contentId: card.contentId,
          title: card.title,
          imageUrl: card.imageUrl,
          category: card.category,
          regionLabel: card.regionLabel,
        });
      }
      router.push(`/spots/${contentId}`);
    },
    [cards, curation.data],
  );

  const onRefresh = useCallback(() => {
    void queryClient.invalidateQueries({
      predicate: (q) => {
        const root = String(q.queryKey[0]);
        return root.startsWith("home-") || root === "channels";
      },
    });
  }, []);

  const toggleScope = useCallback(() => {
    setScope((current) => (current === "nearby" ? "national" : "nearby"));
    if (effectiveScope === "national" && !coords) void request();
  }, [effectiveScope, coords, request]);

  return (
    <View style={styles.root}>
      <AppBar />
      <ScrollView
        ref={listRef}
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl
            refreshing={active.isFetching && !active.isLoading}
            onRefresh={onRefresh}
            tintColor={colors.ter}
          />
        }
      >
        <View style={styles.header}>
          <View style={styles.headerCopy}>
            <Text style={styles.kicker}>{todayLine(regionLabel)}</Text>
            <Pressable
              testID="home-scope"
              accessibilityRole="button"
              accessibilityLabel={`${scopeTitle(effectiveScope)}, 눌러서 범위 바꾸기`}
              hitSlop={6}
              style={({ pressed }) => [styles.titleRow, pressed && styles.pressed]}
              onPress={toggleScope}
            >
              <Text style={styles.title}>{scopeTitle(effectiveScope)}</Text>
              <Icon name="chevron-down" size={20} color={colors.ter} strokeWidth={1.9} />
            </Pressable>
          </View>
        </View>

        {locationDenied && scope === "nearby" ? (
          <Pressable
            testID="home-location-cta"
            onPress={() => void request()}
            style={styles.permit}
          >
            <Icon name="location" size={18} color={colors.accentText} />
            <Text style={styles.permitText}>{LOCATION_CTA}</Text>
            <Icon name="chevron-right" size={16} color={colors.ter} />
          </Pressable>
        ) : null}

        {active.isLoading || waitingForFix ? (
          <EditorialRailSkeleton testID="home-rank-skeleton" />
        ) : cards.length > 0 ? (
          <EditorialRail
            testID="home-rank-rail"
            kicker={RANK_KICKER}
            title={effectiveScope === "nearby" ? "주변 인기 순위" : "전국 인기 순위"}
            subtitle={formatBaseDate(active.data?.baseDate)}
            items={shown}
            onOpenSpot={openSpot}
            compact
          />
        ) : (
          <RankList
            title={effectiveScope === "nearby" ? "주변 인기 순위" : "전국 인기 순위"}
            note={null}
            cards={shown}
            isLoading={false}
            isError={active.isError}
            onRetry={() => void active.refetch()}
            onOpenSpot={openSpot}
          />
        )}

        {curation.isLoading || curation.data?.items.length ? (
          <>
            <View style={styles.sectionGap} />
            <CurationSection
              data={curation.data}
              isLoading={curation.isLoading}
              onOpenSpot={openSpot}
            />
          </>
        ) : null}

        <View style={styles.sectionGap} />

        <View style={styles.channels}>
          <ChannelChips coords={coords} onOpen={(key) => router.push(`/channels?start=${key}`)} />
        </View>

        <AiSection
          displayName={displayName}
          data={recommendations.data}
          isLoading={recommendations.isLoading}
          isError={recommendations.isError}
          onRetry={() => void recommendations.refetch()}
        />
      </ScrollView>
    </View>
  );
}

function findCard(
  contentId: string,
  cards: HomeSpotCard[],
  curated: HomeSpotCard[] | undefined,
): HomeSpotCard | null {
  return (
    cards.find((c) => c.contentId === contentId) ??
    curated?.find((c) => c.contentId === contentId) ??
    null
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  content: { paddingTop: spacing.xs, paddingBottom: spacing.xxl },
  header: { paddingHorizontal: spacing.lg, paddingTop: spacing.md, paddingBottom: 22 },
  headerCopy: { flex: 1, minWidth: 0 },
  kicker: { fontSize: 11.5, fontWeight: "700", color: colors.ter },
  titleRow: { flexDirection: "row", alignItems: "center", gap: 4, marginTop: 6 },
  title: { fontSize: 26, fontWeight: "800", letterSpacing: -0.9, color: colors.ink },
  gap: { height: spacing.xl },
  sectionGap: { height: SECTION_GAP },
  channels: { paddingBottom: spacing.xs },
  expand: {
    marginHorizontal: spacing.lg,
    marginTop: spacing.md,
    height: 48,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    borderRadius: 14,
    backgroundColor: colors.fill,
  },
  expandText: { fontSize: 14.5, fontWeight: "700", letterSpacing: -0.3, color: colors.sec },
  permit: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
    paddingHorizontal: spacing.md,
    height: 52,
    borderRadius: 14,
    backgroundColor: colors.accentFill,
  },
  permitText: { flex: 1, fontSize: 13.5, fontWeight: "700", color: colors.ink },
  pressed: { opacity: 0.7 },
});
