import { useState } from "react";
import { Pressable, StyleSheet, Text, View, useWindowDimensions } from "react-native";
import { Icon } from "@/components/Icon";
import { PrimaryButton } from "@/components/PrimaryButton";
import { Skeleton } from "@/components/Skeleton";
import { SectionHead } from "@/features/home/components/SectionHead";
import { SpotGrid } from "@/features/home/components/SpotGrid";
import { distanceSubtitle } from "@/features/home/lib/card-subtitle";
import type { HomeSpotCard } from "@/features/home/api";
import { colors, spacing } from "@/constants/theme";

interface Props {
  title: string;
  note: string | null;
  cards: HomeSpotCard[];
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
}

const COLLAPSED_COUNT = 4;

export function RankSection({ title, note, cards, isLoading, isError, onRetry }: Props) {
  const [expanded, setExpanded] = useState(false);
  const shown = expanded ? cards : cards.slice(0, COLLAPSED_COUNT);
  const hiddenCount = cards.length - COLLAPSED_COUNT;

  return (
    <View>
      <SectionHead title={title} note={note} />
      {isLoading ? (
        <GridSkeleton />
      ) : isError ? (
        <View style={styles.error}>
          <Text style={styles.errorText}>인기 장소를 불러오지 못했어요.</Text>
          <PrimaryButton testID="home-rank-retry" label="다시 시도" onPress={onRetry} />
        </View>
      ) : cards.length === 0 ? (
        <Text style={styles.empty}>지금은 보여줄 장소가 없어요.</Text>
      ) : (
        <>
          <SpotGrid cards={shown} subtitleOf={distanceSubtitle} />
          {hiddenCount > 0 ? (
            <Pressable
              testID="home-rank-expand"
              accessibilityRole="button"
              onPress={() => setExpanded((v) => !v)}
              style={styles.expand}
            >
              <Text style={styles.expandText}>
                {expanded ? "접기" : `5~${cards.length}위 더보기`}
              </Text>
              <Icon name={expanded ? "chevron-up" : "chevron-down"} size={16} color={colors.sec} />
            </Pressable>
          ) : null}
        </>
      )}
    </View>
  );
}

export function GridSkeleton() {
  const { width } = useWindowDimensions();
  const cardWidth = Math.floor((width - spacing.lg * 2 - 10) / 2);
  return (
    <View style={styles.skeletonGrid}>
      {[0, 1, 2, 3].map((i) => (
        <Skeleton
          key={i}
          width={cardWidth}
          height={Math.round(cardWidth * 1.08) + 62}
          radius={16}
        />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  expand: {
    marginHorizontal: spacing.lg,
    marginTop: spacing.md,
    height: 52,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    borderRadius: 16,
    backgroundColor: colors.fill,
  },
  expandText: { fontSize: 15, fontWeight: "700", letterSpacing: -0.3, color: colors.sec },
  error: { alignItems: "center", gap: spacing.md, paddingHorizontal: spacing.lg },
  errorText: { fontSize: 14, color: colors.sec },
  empty: { paddingHorizontal: spacing.lg, fontSize: 14, color: colors.sec },
  skeletonGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 10,
    paddingHorizontal: spacing.lg,
  },
});
