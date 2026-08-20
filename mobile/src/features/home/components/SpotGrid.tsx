import { StyleSheet, View, useWindowDimensions } from "react-native";
import { router } from "expo-router";
import { Skeleton } from "@/components/Skeleton";
import { SpotGridCard } from "@/features/home/components/SpotGridCard";
import type { HomeSpotCard } from "@/features/home/api";
import { prefetchSpot } from "@/features/spots/queries";
import { spacing } from "@/constants/theme";

interface Props {
  cards: HomeSpotCard[];
  subtitleOf: (card: HomeSpotCard) => string;
}

const GUTTER = 10;
const GRID_PADDING = spacing.lg;

export function SpotGrid({ cards, subtitleOf }: Props) {
  const { width } = useWindowDimensions();
  const cardWidth = Math.floor((width - GRID_PADDING * 2 - GUTTER) / 2);

  const open = (card: HomeSpotCard) => {
    prefetchSpot({
      contentId: card.contentId,
      title: card.title,
      imageUrl: card.imageUrl,
      category: card.category,
      regionLabel: card.regionLabel,
    });
    router.push(`/spots/${card.contentId}`);
  };

  return (
    <View style={styles.grid}>
      {cards.map((card) => (
        <SpotGridCard
          key={card.contentId}
          card={card}
          width={cardWidth}
          subtitle={subtitleOf(card)}
          onPress={() => open(card)}
        />
      ))}
    </View>
  );
}

export function GridSkeleton() {
  const { width } = useWindowDimensions();
  const cardWidth = Math.floor((width - GRID_PADDING * 2 - GUTTER) / 2);
  return (
    <View style={styles.grid}>
      {[0, 1, 2, 3].map((slot) => (
        <Skeleton
          key={slot}
          width={cardWidth}
          height={Math.round(cardWidth * 1.08) + 62}
          radius={16}
        />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: GUTTER,
    paddingHorizontal: GRID_PADDING,
  },
});
