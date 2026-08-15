import { useEffect, useMemo, useRef, useState } from "react";
import {
  View,
  Text,
  Pressable,
  FlatList,
  useWindowDimensions,
  StyleSheet,
  type NativeSyntheticEvent,
  type NativeScrollEvent,
} from "react-native";
import { Image } from "expo-image";
import { fullSizeSourceUri } from "@/components/RemoteImage";
import { Icon } from "@/components/Icon";
import { useMatches } from "@/features/feed/posts-queries";
import { useSaveOptimistic } from "@/features/saved/hooks/use-save-optimistic";
import type { OverseasPost } from "@/features/feed/posts-api";
import { PostSlide, type Slide } from "@/features/feed/components/PostSlide";
import { CreditSheet } from "@/features/feed/components/CreditSheet";
import { colors, shadows } from "@/constants/theme";

const CARD_HEIGHT = 520;

function slidesFor(post: OverseasPost, matches: ReturnType<typeof useMatches>["data"]): Slide[] {
  const hero: Slide = { kind: "hero", post };
  if (!matches) {
    return [hero, { kind: "skeleton" }];
  }
  if (matches.matches.length === 0) {
    return [hero, { kind: "empty" }];
  }
  return [
    hero,
    ...matches.matches.map((m, i) => ({ kind: "match", match: m, number: i + 1 }) as Slide),
  ];
}

export function PostCarousel({
  post,
  onNavigate,
}: {
  post: OverseasPost;
  onNavigate?: () => void;
}) {
  const { width } = useWindowDimensions();
  const cardWidth = width - 32;
  const [restedIndex, setRestedIndex] = useState(0);
  const [armed, setArmed] = useState(false);
  const [creditOpen, setCreditOpen] = useState(false);
  const listRef = useRef<FlatList<Slide>>(null);

  const { data } = useMatches(post.id, { enabled: armed });
  const slides = useMemo(() => slidesFor(post, data), [post, data]);
  const counted = (data?.matches.length ?? 0) > 0;

  const lastIndex = slides.length - 1;
  const index = Math.min(restedIndex, lastIndex);
  const active = slides[index];

  useEffect(() => {
    if (restedIndex <= lastIndex) return;
    listRef.current?.scrollToIndex({ index: lastIndex, animated: false });
  }, [restedIndex, lastIndex]);

  useEffect(() => {
    for (const m of data?.matches.slice(0, 2) ?? []) {
      if (m.imageUrl)
        void Image.prefetch(fullSizeSourceUri(m.imageUrl), { cachePolicy: "memory-disk" });
    }
  }, [data]);

  const settleTo = (x: number) => {
    const next = cardWidth > 0 ? Math.round(x / cardWidth) : 0;
    setRestedIndex((prev) => (prev === next ? prev : next));
  };
  const onScroll = (e: NativeSyntheticEvent<NativeScrollEvent>) =>
    settleTo(e.nativeEvent.contentOffset.x);
  const onScrollBeginDrag = () => setArmed(true);
  const onMomentumEnd = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    const x = e.nativeEvent.contentOffset.x;
    settleTo(x);
    if (cardWidth > 0 && Math.round(x / cardWidth) >= 1) setArmed(true);
  };

  return (
    <View style={styles.wrap}>
      <View style={[styles.card, { width: cardWidth, height: CARD_HEIGHT }]}>
        <FlatList
          ref={listRef}
          data={slides}
          keyExtractor={(s, i) => `${s.kind}-${i}`}
          horizontal
          pagingEnabled
          scrollEnabled={slides.length > 1}
          showsHorizontalScrollIndicator={false}
          getItemLayout={(_, i) => ({ length: cardWidth, offset: cardWidth * i, index: i })}
          onScroll={onScroll}
          scrollEventThrottle={16}
          onScrollBeginDrag={onScrollBeginDrag}
          onMomentumScrollEnd={onMomentumEnd}
          renderItem={({ item }) => (
            <PostSlide slide={item} width={cardWidth} onNavigate={onNavigate} />
          )}
        />

        {active?.kind === "hero" ? (
          <Pressable
            testID="credit-info"
            style={styles.info}
            onPress={() => setCreditOpen(true)}
            hitSlop={8}
          >
            <Icon name="info" size={18} color={colors.onImage} strokeWidth={1.8} />
          </Pressable>
        ) : null}
        {active?.kind === "match" ? (
          <SaveButton key={active.match.contentId} contentId={active.match.contentId} />
        ) : null}
        {counted ? (
          <View style={styles.counter} pointerEvents="none">
            <Text testID="post-counter" style={styles.counterText}>
              {`${index + 1}/${slides.length}`}
            </Text>
          </View>
        ) : null}
      </View>

      {counted ? (
        <View style={styles.dots}>
          {slides.map((s, i) => (
            <View
              key={`${s.kind}-${i}`}
              testID="carousel-dot"
              style={[styles.dot, i === index ? styles.dotActive : styles.dotIdle]}
            />
          ))}
        </View>
      ) : null}

      <CreditSheet visible={creditOpen} post={post} onClose={() => setCreditOpen(false)} />
    </View>
  );
}

function SaveButton({ contentId }: { contentId: string }) {
  const { saved, toggle } = useSaveOptimistic(contentId);

  return (
    <Pressable
      testID="match-save"
      style={styles.save}
      onPress={() => void toggle()}
      hitSlop={8}
      accessibilityLabel="저장"
    >
      <Icon
        name={saved ? "bookmark-fill" : "bookmark"}
        size={19}
        color={colors.onImage}
        strokeWidth={1.8}
      />
    </Pressable>
  );
}

const GLASS = {
  backgroundColor: colors.glassFill,
  borderWidth: 1,
  borderColor: colors.glassBorder,
} as const;

const styles = StyleSheet.create({
  wrap: { marginHorizontal: 16 },
  card: {
    borderRadius: 16,
    overflow: "hidden",
    backgroundColor: colors.inset,
    ...shadows.card,
  },
  counter: {
    position: "absolute",
    top: 14,
    right: 14,
    height: 28,
    paddingHorizontal: 11,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.control,
  },
  counterText: { fontSize: 12, fontWeight: "700", color: colors.onImage },
  info: {
    position: "absolute",
    top: 14,
    left: 14,
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
    ...GLASS,
  },
  save: {
    position: "absolute",
    top: 14,
    left: 14,
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
    ...GLASS,
  },
  dots: { flexDirection: "row", alignSelf: "center", gap: 6, marginTop: 12 },
  dot: { width: 6, height: 6, borderRadius: 3 },
  dotActive: { backgroundColor: colors.ink },
  dotIdle: { backgroundColor: colors.line },
});
