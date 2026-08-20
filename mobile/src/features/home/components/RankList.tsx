import { Pressable, StyleSheet, Text, View } from "react-native";
import { PrimaryButton } from "@/components/PrimaryButton";
import { RemoteImage } from "@/components/RemoteImage";
import { Skeleton } from "@/components/Skeleton";
import { SectionHead } from "@/features/home/components/SectionHead";
import type { HomeSpotCard } from "@/features/home/api";
import { colors, spacing } from "@/constants/theme";

export const LOAD_FAILED = "인기 장소를 불러오지 못했어요.";
export const EMPTY = "지금은 보여줄 장소가 없어요.";
export const HOT_RANKS = 3;

const SKELETON_ROWS = [0, 1, 2, 3, 4, 5];

interface Props {
  title: string;
  note: string | null;
  cards: HomeSpotCard[];
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
  onOpenSpot: (contentId: string) => void;
}

export function distanceLabel(dist: number | null): string {
  if (dist === null || dist <= 0) return "";
  return dist < 1000 ? `${Math.round(dist)}m` : `${(dist / 1000).toFixed(1)}km`;
}

export function RankList({ title, note, cards, isLoading, isError, onRetry, onOpenSpot }: Props) {
  return (
    <View>
      <SectionHead title={title} note={note} />
      {isLoading ? (
        <View testID="home-rank-skeleton">
          {SKELETON_ROWS.map((slot) => (
            <View key={slot} style={styles.row}>
              <View style={styles.rank} />
              <Skeleton width={46} height={46} radius={10} />
              <View style={styles.copy}>
                <Skeleton width={140} height={13} radius={5} />
              </View>
            </View>
          ))}
        </View>
      ) : isError ? (
        <View style={styles.error}>
          <Text style={styles.errorText}>{LOAD_FAILED}</Text>
          <PrimaryButton testID="home-rank-retry" label="다시 시도" onPress={onRetry} />
        </View>
      ) : cards.length === 0 ? (
        <Text style={styles.empty}>{EMPTY}</Text>
      ) : (
        cards.map((card, index) => (
          <Pressable
            key={card.contentId}
            testID="home-rank-row"
            accessibilityRole="button"
            accessibilityLabel={`${index + 1}위 ${card.title}`}
            style={({ pressed }) => [styles.row, pressed && styles.pressed]}
            onPress={() => onOpenSpot(card.contentId)}
          >
            <Text style={[styles.rank, index < HOT_RANKS && styles.rankHot]}>{index + 1}</Text>
            <RemoteImage uri={card.imageUrl} style={styles.thumb} radius={10} midSize />
            <View style={styles.copy}>
              <Text style={styles.title} numberOfLines={1}>
                {card.title}
              </Text>
              <Text style={styles.note} numberOfLines={1}>
                {[card.category ?? card.tag, card.regionLabel].filter(Boolean).join(" · ")}
              </Text>
            </View>
            <Text style={styles.distance}>{distanceLabel(card.dist)}</Text>
          </Pressable>
        ))
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 11,
    paddingHorizontal: spacing.lg,
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  rank: {
    width: 16,
    textAlign: "right",
    fontSize: 12.5,
    fontWeight: "700",
    fontVariant: ["tabular-nums"],
    color: colors.ter,
  },
  rankHot: { color: colors.accentText },
  thumb: { width: 46, height: 46 },
  copy: { flex: 1, minWidth: 0, gap: 2 },
  title: { fontSize: 14, fontWeight: "700", letterSpacing: -0.3, color: colors.ink },
  note: { fontSize: 11.5, fontWeight: "600", color: colors.ter },
  distance: {
    fontSize: 11,
    fontWeight: "700",
    fontVariant: ["tabular-nums"],
    color: colors.sec,
  },
  error: { alignItems: "center", gap: spacing.md, paddingHorizontal: spacing.lg },
  errorText: { fontSize: 14, color: colors.sec },
  empty: { paddingHorizontal: spacing.lg, fontSize: 14, color: colors.sec },
  pressed: { opacity: 0.7 },
});
