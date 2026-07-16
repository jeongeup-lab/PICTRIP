import { useEffect, useMemo, useState } from "react";
import {
  View,
  FlatList,
  useWindowDimensions,
  StyleSheet,
  type NativeSyntheticEvent,
  type NativeScrollEvent,
} from "react-native";
import { Image } from "expo-image";
import { fullSizeSourceUri } from "@/components/RemoteImage";
import { useMatches } from "@/features/feed/posts-queries";
import type { OverseasPost } from "@/features/feed/posts-api";
import { PostSlide, type Slide } from "@/features/feed/components/PostSlide";
import { CreditSheet } from "@/features/feed/components/CreditSheet";
import { colors, shadows } from "@/constants/theme";

const CARD_HEIGHT = 520;

function slidesFor(post: OverseasPost, matches: ReturnType<typeof useMatches>["data"]): Slide[] {
  const hero: Slide = { kind: "hero", post };
  if (!matches) {
    return [hero, { kind: "skeleton" }, { kind: "skeleton" }, { kind: "skeleton" }];
  }
  if (matches.matches.length === 0) {
    return [hero];
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
  const [index, setIndex] = useState(0);
  const [armed, setArmed] = useState(false);
  const [creditOpen, setCreditOpen] = useState(false);

  const { data } = useMatches(post.id, { enabled: armed });
  const slides = useMemo(() => slidesFor(post, data), [post, data]);
  const counted = !!data && slides.length > 1;

  useEffect(() => {
    for (const m of data?.matches.slice(0, 2) ?? []) {
      if (m.imageUrl)
        void Image.prefetch(fullSizeSourceUri(m.imageUrl), { cachePolicy: "memory-disk" });
    }
  }, [data]);

  const onScrollBeginDrag = () => setArmed(true);
  const onMomentumEnd = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    const i = cardWidth > 0 ? Math.round(e.nativeEvent.contentOffset.x / cardWidth) : 0;
    if (i !== index) setIndex(i);
    if (i >= 1) setArmed(true);
  };

  return (
    <View style={styles.wrap}>
      <View style={[styles.card, { width: cardWidth, height: CARD_HEIGHT }]}>
        <FlatList
          data={slides}
          keyExtractor={(s, i) => `${s.kind}-${i}`}
          horizontal
          pagingEnabled
          scrollEnabled={slides.length > 1}
          showsHorizontalScrollIndicator={false}
          getItemLayout={(_, i) => ({ length: cardWidth, offset: cardWidth * i, index: i })}
          onScrollBeginDrag={onScrollBeginDrag}
          onMomentumScrollEnd={onMomentumEnd}
          renderItem={({ item, index: i }) => (
            <PostSlide
              slide={item}
              width={cardWidth}
              counter={counted ? `${i + 1}/${slides.length}` : ""}
              onInfo={() => setCreditOpen(true)}
              onNavigate={onNavigate}
            />
          )}
        />
      </View>

      {counted ? (
        <View style={styles.dots}>
          {slides.map((s, i) => (
            <View
              key={`${s.kind}-${i}`}
              style={[styles.dot, i === index ? styles.dotActive : styles.dotIdle]}
            />
          ))}
        </View>
      ) : null}

      <CreditSheet visible={creditOpen} post={post} onClose={() => setCreditOpen(false)} />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { marginHorizontal: 16 },
  card: {
    borderRadius: 16,
    overflow: "hidden",
    backgroundColor: colors.inset,
    ...shadows.card,
  },
  dots: { flexDirection: "row", alignSelf: "center", gap: 6, marginTop: 12 },
  dot: { width: 6, height: 6, borderRadius: 3 },
  dotActive: { backgroundColor: colors.ink },
  dotIdle: { backgroundColor: colors.line },
});
