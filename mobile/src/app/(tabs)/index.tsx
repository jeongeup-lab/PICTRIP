import { useCallback, useRef, useState } from "react";
import { FlatList, RefreshControl, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router, useScrollToTop } from "expo-router";
import { ChannelTiles } from "@/features/channels/components/ChannelTiles";
import type { ShortsCardData } from "@/features/shorts/api";
import { ShortsCard } from "@/features/shorts/components/ShortsCard";
import { ShortsPlayerSheet } from "@/features/shorts/components/ShortsPlayerSheet";
import { useShortsFeed } from "@/features/shorts/queries";
import { Skeleton } from "@/components/Skeleton";
import { PrimaryButton } from "@/components/PrimaryButton";
import { queryClient } from "@/lib/query-client";
import { colors, spacing } from "@/constants/theme";

function Header() {
  return (
    <View style={styles.headerBlock}>
      <ChannelTiles onOpen={(key) => router.push(`/channels?start=${key}`)} />
    </View>
  );
}

export default function HomeScreen() {
  const listRef = useRef<FlatList<ShortsCardData>>(null);
  const [openShort, setOpenShort] = useState<ShortsCardData | null>(null);

  useScrollToTop(listRef);

  const {
    data,
    isLoading,
    isError,
    isFetching,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
    refetch,
  } = useShortsFeed();

  const shorts: ShortsCardData[] = data?.pages.flatMap((p) => p.items) ?? [];

  const onRefresh = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["shorts"] });
  }, []);

  const onEndReached = () => {
    if (hasNextPage && !isFetching) void fetchNextPage();
  };

  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      <View style={styles.bar}>
        <Text style={styles.wordmark}>PICTRIP</Text>
      </View>

      {isLoading ? (
        <View style={styles.loading}>
          <View style={styles.tileRow}>
            <Skeleton width={86} height={110} radius={14} />
            <Skeleton width={86} height={110} radius={14} />
            <Skeleton width={86} height={110} radius={14} />
          </View>
          <Skeleton height={520} radius={16} style={{ marginTop: spacing.xxl }} />
        </View>
      ) : isError || !data ? (
        <View style={styles.error}>
          <Text style={styles.errorText}>피드를 불러오지 못했어요.</Text>
          <PrimaryButton testID="home-retry" label="다시 시도" onPress={() => refetch()} />
        </View>
      ) : (
        <FlatList
          ref={listRef}
          data={shorts}
          keyExtractor={(short) => short.videoId}
          renderItem={({ item }) => (
            <View style={styles.cardBlock}>
              <ShortsCard short={item} onOpen={setOpenShort} />
            </View>
          )}
          ListHeaderComponent={Header}
          showsVerticalScrollIndicator={false}
          onEndReached={onEndReached}
          onEndReachedThreshold={0.8}
          refreshControl={
            <RefreshControl
              refreshing={isFetching && !isLoading && !isFetchingNextPage}
              onRefresh={onRefresh}
              tintColor={colors.ter}
            />
          }
        />
      )}

      <ShortsPlayerSheet short={openShort} onClose={() => setOpenShort(null)} />
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
  headerBlock: { paddingTop: spacing.md, paddingBottom: spacing.sm },
  cardBlock: { paddingBottom: spacing.xxl },
  loading: { padding: spacing.lg },
  tileRow: { flexDirection: "row", gap: 10 },
  error: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.md,
    padding: spacing.xl,
  },
  errorText: { fontSize: 15, color: colors.sec },
});
