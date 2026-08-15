import { useCallback, useRef, useState } from "react";
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router, useScrollToTop } from "expo-router";
import { Icon } from "@/components/Icon";
import { ChannelTiles } from "@/features/channels/components/ChannelTiles";
import { AiSection } from "@/features/home/components/AiSection";
import { RankSection } from "@/features/home/components/RankSection";
import { ScopeTabs, type HomeScope } from "@/features/home/components/ScopeTabs";
import { useHomeLocation } from "@/features/home/hooks/use-home-location";
import { formatBaseDate } from "@/features/home/lib/base-date";
import {
  useNearby,
  useRecommendations,
  useRegionLabel,
  useTrending,
} from "@/features/home/queries";
import { useAuthStore } from "@/features/auth/stores/auth-store";
import { queryClient } from "@/lib/query-client";
import { colors, spacing } from "@/constants/theme";

export default function HomeScreen() {
  const listRef = useRef<ScrollView>(null);
  useScrollToTop(listRef);

  const [scope, setScope] = useState<HomeScope>("nearby");
  const { coords, status, request } = useHomeLocation();
  const displayName = useAuthStore((s) => s.user?.displayName ?? null);

  const region = useRegionLabel(coords);
  const nearby = useNearby(coords);
  const national = useTrending();
  const recommendations = useRecommendations(coords);

  const locationDenied = status === "denied" || status === "undetermined";
  const nearbyIsEmpty =
    !nearby.isLoading && !nearby.isError && (nearby.data?.items.length ?? 0) === 0;
  const showNational = scope === "national" || locationDenied || (!!coords && nearbyIsEmpty);
  const active = showNational ? national : nearby;
  const waitingForFix = !showNational && !coords;
  const cards = active.data?.items ?? [];
  const regionLabel = region.data?.label ?? null;

  const onRefresh = useCallback(() => {
    void queryClient.invalidateQueries({
      predicate: (q) => {
        const root = String(q.queryKey[0]);
        return root.startsWith("home-") || root === "channels";
      },
    });
  }, []);

  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      <View style={styles.bar}>
        <Text style={styles.wordmark}>PICTRIP</Text>
      </View>

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
        <View style={styles.channels}>
          <ChannelTiles onOpen={(key) => router.push(`/channels?start=${key}`)} />
        </View>

        <ScopeTabs
          scope={showNational ? "national" : "nearby"}
          nearbyLabel={regionLabel ?? "내 주변"}
          onChange={(next) => {
            setScope(next);
            if (next === "nearby" && !coords) void request();
          }}
        />

        {locationDenied && scope === "nearby" ? (
          <Pressable
            testID="home-location-cta"
            onPress={() => void request()}
            style={styles.permit}
          >
            <Icon name="location" size={18} color={colors.accentText} />
            <Text style={styles.permitText}>위치를 켜면 지금 주변 인기 장소를 보여드려요</Text>
            <Icon name="chevron-right" size={16} color={colors.ter} />
          </Pressable>
        ) : null}

        <RankSection
          title={
            showNational
              ? "전국 인기 장소"
              : regionLabel
                ? `${regionLabel} 근처 인기 장소`
                : "지금 주변 인기 장소"
          }
          note={cards.length > 0 ? formatBaseDate(active.data?.baseDate) : null}
          cards={cards}
          isLoading={active.isLoading || waitingForFix}
          isError={active.isError}
          onRetry={() => void active.refetch()}
        />

        <AiSection
          displayName={displayName}
          data={recommendations.data}
          isLoading={recommendations.isLoading}
          isError={recommendations.isError}
          onRetry={() => void recommendations.refetch()}
        />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  bar: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    alignItems: "center",
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  wordmark: { fontSize: 20, fontWeight: "800", letterSpacing: -0.5, color: colors.ink },
  content: { paddingTop: spacing.md, paddingBottom: spacing.xxl },
  channels: { paddingBottom: spacing.lg },
  permit: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginHorizontal: spacing.lg,
    marginTop: spacing.md,
    paddingHorizontal: spacing.md,
    height: 52,
    borderRadius: 14,
    backgroundColor: colors.accentFill,
  },
  permitText: { flex: 1, fontSize: 13.5, fontWeight: "700", color: colors.ink },
});
