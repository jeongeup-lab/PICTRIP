import { useCallback, useState } from "react";
import { FlatList, View, Text, RefreshControl, StyleSheet, type ViewToken } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router } from "expo-router";
import { ChannelTiles } from "@/features/channels/components/ChannelTiles";
import { PostCarousel } from "@/features/feed/components/PostCarousel";
import { prefetchMatches, usePostsFeed } from "@/features/feed/posts-queries";
import type { OverseasPost } from "@/features/feed/posts-api";
import { Skeleton } from "@/components/Skeleton";
import { PrimaryButton } from "@/components/PrimaryButton";
import { queryClient } from "@/lib/query-client";
import { makeSeed } from "@/lib/seed";
import { colors, spacing } from "@/constants/theme";

const VIEWABILITY = { itemVisiblePercentThreshold: 30 };

function Header() {
  return (
    <View style={styles.headerBlock}>
      <ChannelTiles onOpen={(key) => router.push(`/channels?start=${key}`)} />
    </View>
  );
}

export default function HomeScreen() {
  const [seed, setSeed] = useState(() => makeSeed());

  const {
    data,
    isLoading,
    isError,
    isFetching,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
    refetch,
  } = usePostsFeed(seed);

  const posts: OverseasPost[] = data?.pages.flatMap((p) => p.items) ?? [];

  const onRefresh = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["matches"] });
    setSeed(makeSeed());
  }, []);

  const onViewableItemsChanged = useCallback(
    ({ viewableItems }: { viewableItems: ViewToken[] }) => {
      for (const token of viewableItems) {
        const post = token.item as OverseasPost | undefined;
        if (post) prefetchMatches(post.id);
      }
    },
    [],
  );

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
          data={posts}
          keyExtractor={(post) => String(post.id)}
          renderItem={({ item }) => (
            <View style={styles.cardBlock}>
              <PostCarousel post={item} />
            </View>
          )}
          ListHeaderComponent={Header}
          showsVerticalScrollIndicator={false}
          onViewableItemsChanged={onViewableItemsChanged}
          viewabilityConfig={VIEWABILITY}
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
