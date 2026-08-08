import { useCallback, useEffect, useMemo, useRef } from "react";
import {
  FlatList,
  View,
  StyleSheet,
  type NativeScrollEvent,
  type NativeSyntheticEvent,
} from "react-native";
import { Skeleton } from "@/components/Skeleton";
import {
  CARD_GAP,
  CARD_HEIGHT,
  CARD_STRIDE,
  CARD_WIDTH,
  SpotCard,
} from "@/features/travel/components/SpotCard";
import { spotDistanceKm } from "@/features/travel/lib/distance";
import type { LatLng } from "@/features/map/lib/geo";
import type { TravelSpot } from "@/features/travel/api";
import { colors, spacing } from "@/constants/theme";

const TRACK_HEIGHT = 3;
const TRACK_TOP_GAP = 9;
const TRACK_BOTTOM_GAP = 11;

export const CAROUSEL_BLOCK_PX = CARD_HEIGHT + TRACK_TOP_GAP + TRACK_HEIGHT + TRACK_BOTTOM_GAP;

const SKELETON_CARDS = [0, 1];

export function SpotCarouselSkeleton() {
  return (
    <View testID="travel-carousel-skeleton" pointerEvents="none">
      <View style={styles.skeletonRow}>
        {SKELETON_CARDS.map((slot) => (
          <Skeleton key={slot} width={CARD_WIDTH} height={CARD_HEIGHT} radius={18} />
        ))}
      </View>
      <View style={styles.track} />
    </View>
  );
}

export function carouselIndexAt(offsetX: number, count: number): number {
  if (count <= 0) return 0;
  const raw = Math.round(offsetX / CARD_STRIDE);
  return Math.min(count - 1, Math.max(0, raw));
}

export function progressRatio(focusedIndex: number, count: number): number {
  if (count <= 0) return 0;
  return ((focusedIndex + 1) / count) * 100;
}

interface Props {
  spots: TravelSpot[];
  tagBasis: string | null;
  focusedIndex: number;
  origin: LatLng | null;
  scrollToIndex?: number | null;
  onFocusChange: (index: number) => void;
  onDetail: (spot: TravelSpot) => void;
  onSaveToggle: (saved: boolean) => void;
  onMetricPress: (tooltip: string) => void;
}

export function SpotCarousel({
  spots,
  tagBasis,
  focusedIndex,
  origin,
  scrollToIndex,
  onFocusChange,
  onDetail,
  onSaveToggle,
  onMetricPress,
}: Props) {
  const listRef = useRef<FlatList<TravelSpot>>(null);
  const reported = useRef(focusedIndex);

  const offsets = useMemo(() => spots.map((_, index) => index * CARD_STRIDE), [spots]);

  useEffect(() => {
    reported.current = focusedIndex;
  }, [spots, focusedIndex]);

  useEffect(() => {
    if (scrollToIndex === null || scrollToIndex === undefined) return;
    if (scrollToIndex < 0 || scrollToIndex >= spots.length) return;
    reported.current = scrollToIndex;
    listRef.current?.scrollToOffset({ offset: scrollToIndex * CARD_STRIDE, animated: true });
  }, [scrollToIndex, spots.length]);

  const onMomentumScrollEnd = useCallback(
    (event: NativeSyntheticEvent<NativeScrollEvent>) => {
      const next = carouselIndexAt(event.nativeEvent.contentOffset.x, spots.length);
      if (next === reported.current) return;
      reported.current = next;
      onFocusChange(next);
    },
    [spots.length, onFocusChange],
  );

  if (spots.length === 0) return null;

  const ratio = progressRatio(focusedIndex, spots.length);

  return (
    <View testID="travel-carousel">
      <FlatList
        ref={listRef}
        data={spots}
        horizontal
        showsHorizontalScrollIndicator={false}
        decelerationRate="fast"
        snapToOffsets={offsets}
        snapToAlignment="start"
        contentContainerStyle={styles.content}
        keyExtractor={(spot) => spot.contentId}
        getItemLayout={(_, index) => ({
          length: CARD_WIDTH,
          offset: index * CARD_STRIDE,
          index,
        })}
        onMomentumScrollEnd={onMomentumScrollEnd}
        renderItem={({ item, index }) => (
          <SpotCard
            spot={item}
            index={index}
            tagBasis={tagBasis}
            distanceKm={spotDistanceKm(item, origin)}
            focused={index === focusedIndex}
            onDetail={() => onDetail(item)}
            onSaveToggle={onSaveToggle}
            onMetricPress={onMetricPress}
          />
        )}
      />

      <View style={styles.track}>
        <View testID="travel-progress-fill" style={[styles.fill, { width: `${ratio}%` }]} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  content: { gap: CARD_GAP, paddingHorizontal: spacing.md },
  skeletonRow: {
    flexDirection: "row",
    gap: CARD_GAP,
    paddingHorizontal: spacing.md,
    overflow: "hidden",
  },
  track: {
    height: TRACK_HEIGHT,
    marginTop: TRACK_TOP_GAP,
    marginHorizontal: spacing.md + 4,
    marginBottom: TRACK_BOTTOM_GAP,
    borderRadius: 2,
    backgroundColor: colors.fillStrong,
    overflow: "hidden",
  },
  fill: { height: TRACK_HEIGHT, minWidth: 14, borderRadius: 2, backgroundColor: colors.onDim },
});
