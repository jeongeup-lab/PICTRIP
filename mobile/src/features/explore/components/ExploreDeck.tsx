import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  FlatList,
  Pressable,
  StatusBar,
  StyleSheet,
  Text,
  View,
  type LayoutChangeEvent,
  type NativeScrollEvent,
  type NativeSyntheticEvent,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router, useScrollToTop } from "expo-router";
import { Icon } from "@/components/Icon";
import { PrimaryButton } from "@/components/PrimaryButton";
import { ExploreGridSheet } from "@/features/explore/components/ExploreGridSheet";
import { PostSlide } from "@/features/explore/components/PostSlide";
import { prefetchMatches, useExploreFeed } from "@/features/explore/queries";
import type { OverseasPost } from "@/features/explore/api";
import { makeSeed } from "@/lib/seed";
import { colors, darkColors, spacing } from "@/constants/theme";

export const DECK_BACKGROUND = "#0E1013";
const DOT_TOP = 18;
export const HINT_TEXT = "위로 밀어 다음 사진";
export const LOAD_FAILED = "사진을 불러오지 못했어요.";
const HINT_SWIPES = 2;
const DOT_WINDOW = 7;

export function slideIndexAt(offsetY: number, height: number, count: number): number {
  if (height <= 0 || count <= 0) return 0;
  return Math.min(count - 1, Math.max(0, Math.round(offsetY / height)));
}

export function dotWindowStart(index: number, count: number): number {
  return Math.max(0, Math.min(index - Math.floor(DOT_WINDOW / 2), count - DOT_WINDOW));
}

export function ExploreDeck() {
  const insets = useSafeAreaInsets();
  const [seed] = useState(() => makeSeed());
  const [box, setBox] = useState({ width: 0, height: 0 });
  const [index, setIndex] = useState(0);
  const [swipes, setSwipes] = useState(0);
  const [gridOpen, setGridOpen] = useState(false);
  const listRef = useRef<FlatList<OverseasPost>>(null);

  useScrollToTop(listRef);

  const { data, fetchNextPage, hasNextPage, isFetching, isLoading, isError, refetch } =
    useExploreFeed(seed);

  const posts = useMemo(() => data?.pages.flatMap((page) => page.items) ?? [], [data]);

  useEffect(() => {
    prefetchMatches(posts[index + 1]?.id);
  }, [posts, index]);

  const onLayout = useCallback((event: LayoutChangeEvent) => {
    const { width, height } = event.nativeEvent.layout;
    setBox({ width, height });
  }, []);

  const onMomentumScrollEnd = useCallback(
    (event: NativeSyntheticEvent<NativeScrollEvent>) => {
      const next = slideIndexAt(event.nativeEvent.contentOffset.y, box.height, posts.length);
      setIndex((current) => {
        if (next !== current) setSwipes((count) => count + 1);
        return next;
      });
    },
    [box.height, posts.length],
  );

  const onEndReached = useCallback(() => {
    if (hasNextPage && !isFetching) void fetchNextPage();
  }, [hasNextPage, isFetching, fetchNextPage]);

  const jumpTo = useCallback(
    (target: number) => {
      setGridOpen(false);
      setIndex(target);
      listRef.current?.scrollToOffset({ offset: target * box.height, animated: false });
    },
    [box.height],
  );

  const openSpot = useCallback((contentId: string) => {
    router.push(`/spots/${contentId}`);
  }, []);

  const ready = box.height > 0 && posts.length > 0;
  const dotStart = dotWindowStart(index, posts.length);

  return (
    <View testID="explore-deck-root" style={styles.root} onLayout={onLayout}>
      <StatusBar barStyle="light-content" />

      {ready ? (
        <FlatList
          testID="explore-deck"
          ref={listRef}
          data={posts}
          keyExtractor={(post) => String(post.id)}
          renderItem={({ item, index: at }) => (
            <PostSlide
              post={item}
              width={box.width}
              height={box.height}
              active={at === index}
              onOpenSpot={openSpot}
            />
          )}
          pagingEnabled
          showsVerticalScrollIndicator={false}
          decelerationRate="fast"
          snapToInterval={box.height}
          snapToAlignment="start"
          disableIntervalMomentum
          getItemLayout={(_, at) => ({
            length: box.height,
            offset: box.height * at,
            index: at,
          })}
          initialNumToRender={2}
          windowSize={3}
          maxToRenderPerBatch={2}
          removeClippedSubviews
          onMomentumScrollEnd={onMomentumScrollEnd}
          onEndReached={onEndReached}
          onEndReachedThreshold={2}
        />
      ) : isError ? (
        <View testID="explore-error" style={styles.center}>
          <Text style={styles.errorText}>{LOAD_FAILED}</Text>
          <PrimaryButton testID="explore-retry" label="다시 시도" onPress={() => void refetch()} />
        </View>
      ) : isLoading ? (
        <View testID="explore-loading" style={styles.center} />
      ) : null}

      <View style={[styles.top, { paddingTop: insets.top + 8 }]} pointerEvents="box-none">
        <Pressable
          testID="explore-grid-open"
          accessibilityRole="button"
          accessibilityLabel="격자로 보기"
          hitSlop={8}
          style={({ pressed }) => pressed && styles.pressed}
          onPress={() => setGridOpen(true)}
        >
          <Icon name="grid" size={22} color={darkColors.onImage} strokeWidth={1.9} />
        </Pressable>
      </View>

      {ready ? (
        <View style={[styles.dots, { top: insets.top + DOT_TOP }]} pointerEvents="none">
          {Array.from({ length: Math.min(DOT_WINDOW, posts.length) }, (_, slot) => (
            <View key={slot} style={[styles.dot, dotStart + slot === index && styles.dotOn]} />
          ))}
        </View>
      ) : null}

      {ready && swipes < HINT_SWIPES ? (
        <View testID="explore-hint" style={styles.hint} pointerEvents="none">
          <Icon name="arrow-up" size={18} color={darkColors.onDim} strokeWidth={2} />
          <Text style={styles.hintText}>{HINT_TEXT}</Text>
        </View>
      ) : null}

      {gridOpen ? (
        <ExploreGridSheet
          posts={posts}
          onPick={jumpTo}
          onClose={() => setGridOpen(false)}
          onEndReached={onEndReached}
        />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: DECK_BACKGROUND },
  center: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: 14,
    paddingHorizontal: 40,
  },
  errorText: { fontSize: 14, fontWeight: "600", color: darkColors.sec },
  top: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    paddingHorizontal: spacing.lg,
    paddingBottom: 26,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "flex-end",
  },
  dots: {
    position: "absolute",
    left: 0,
    right: 0,
    flexDirection: "row",
    justifyContent: "center",
    gap: 3,
  },
  dot: { width: 14, height: 2.5, borderRadius: 2, backgroundColor: "rgba(255,255,255,0.32)" },
  dotOn: { width: 22, backgroundColor: colors.onImage },
  hint: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 214,
    alignItems: "center",
    gap: 2,
  },
  hintText: {
    fontSize: 11.5,
    fontWeight: "700",
    color: darkColors.onDim,
    textShadowColor: "rgba(0,0,0,0.6)",
    textShadowRadius: 6,
  },
  pressed: { opacity: 0.6 },
});
