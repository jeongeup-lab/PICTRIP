import { useCallback, useState } from "react";
import {
  FlatList,
  View,
  Text,
  Pressable,
  RefreshControl,
  StyleSheet,
  type ViewToken,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router } from "expo-router";
import { ChannelTiles } from "@/features/channels/components/ChannelTiles";
import { PostCarousel } from "@/features/feed/components/PostCarousel";
import { prefetchMatches, usePostsFeed } from "@/features/feed/posts-queries";
import type { OverseasPost } from "@/features/feed/posts-api";
import { Skeleton } from "@/components/Skeleton";
import { PrimaryButton } from "@/components/PrimaryButton";
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

function Footer() {
  return (
    <View style={styles.footer}>
      <View style={styles.footerLinks}>
        <Pressable
          testID="footer-terms"
          accessibilityRole="link"
          hitSlop={8}
          onPress={() => router.push("/legal/terms")}
        >
          <Text style={styles.footerLink}>이용약관</Text>
        </Pressable>
        <View style={styles.footerSep} />
        <Pressable
          testID="footer-privacy"
          accessibilityRole="link"
          hitSlop={8}
          onPress={() => router.push("/legal/privacy")}
        >
          <Text style={styles.footerLinkStrong}>개인정보처리방침</Text>
        </Pressable>
        <View style={styles.footerSep} />
        <Pressable
          testID="footer-data-source"
          accessibilityRole="link"
          hitSlop={8}
          onPress={() => router.push("/legal/data-sources")}
        >
          <Text style={styles.footerLink}>데이터 출처</Text>
        </Pressable>
      </View>
      <Text style={styles.footerNote}>ⓒ PicTrip</Text>
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

  const onRefresh = useCallback(() => setSeed(makeSeed()), []);

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
        <View style={styles.wordmarkRow}>
          <Text style={styles.wordmark}>PICTRIP</Text>
          <View style={styles.wordmarkDot} />
        </View>
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
          ListFooterComponent={Footer}
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
  wordmarkRow: { flexDirection: "row", alignItems: "flex-end" },
  wordmark: { fontSize: 20, fontWeight: "800", letterSpacing: -0.5, color: colors.ink },
  wordmarkDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    marginLeft: 3,
    marginBottom: 4,
    backgroundColor: colors.accent,
  },
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
  footer: {
    backgroundColor: colors.inset,
    borderTopWidth: 1,
    borderTopColor: colors.line,
    paddingVertical: spacing.lg,
    paddingHorizontal: spacing.lg,
    gap: spacing.sm,
  },
  footerLinks: { flexDirection: "row", alignItems: "center", gap: 12 },
  footerLink: { fontSize: 12, fontWeight: "600", color: colors.sec },
  footerLinkStrong: { fontSize: 12, fontWeight: "700", color: colors.ink },
  footerSep: { width: 1, height: 10, backgroundColor: colors.line },
  footerNote: { fontSize: 11.5, lineHeight: 17, color: colors.ter },
});
