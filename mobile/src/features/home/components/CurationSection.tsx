import { FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import { RemoteImage } from "@/components/RemoteImage";
import { Skeleton } from "@/components/Skeleton";
import type { Curation, HomeSpotCard } from "@/features/home/api";
import { colors, radii, spacing } from "@/constants/theme";

export const CARD_WIDTH = 248;
export const CARD_GAP = 12;

const SKELETONS = [0, 1];

interface Props {
  data: Curation | undefined;
  isLoading: boolean;
  onOpenSpot: (contentId: string) => void;
}

export function CurationSection({ data, isLoading, onOpenSpot }: Props) {
  if (isLoading) return <CurationSkeleton />;
  if (!data || data.items.length === 0) return null;

  return (
    <View testID="home-curation">
      <View style={styles.head}>
        <View style={styles.kick}>
          <Text style={styles.kickText}>{data.kicker}</Text>
          <View style={styles.kickRule} />
        </View>
        <Text style={styles.title}>{data.title}</Text>
        <Text style={styles.subtitle}>{data.subtitle}</Text>
      </View>

      <FlatList
        horizontal
        data={data.items}
        keyExtractor={(card) => card.contentId}
        showsHorizontalScrollIndicator={false}
        snapToInterval={CARD_WIDTH + CARD_GAP}
        decelerationRate="fast"
        contentContainerStyle={styles.track}
        renderItem={({ item, index }) => (
          <CurationCard card={item} index={index} onPress={() => onOpenSpot(item.contentId)} />
        )}
      />
    </View>
  );
}

function CurationCard({
  card,
  index,
  onPress,
}: {
  card: HomeSpotCard;
  index: number;
  onPress: () => void;
}) {
  return (
    <Pressable
      testID="home-curation-card"
      accessibilityRole="button"
      accessibilityLabel={`${card.title} 상세보기`}
      style={({ pressed }) => [styles.card, pressed && styles.pressed]}
      onPress={onPress}
    >
      <View style={styles.imageSlot}>
        <RemoteImage uri={card.imageUrl} style={styles.image} radius={16} />
        <View style={styles.badge}>
          <Text style={styles.badgeText}>{index + 1}</Text>
        </View>
      </View>
      <Text style={styles.cardTitle} numberOfLines={1}>
        {card.title}
      </Text>
      <Text style={styles.cardNote} numberOfLines={1}>
        {card.regionLabel}
      </Text>
    </Pressable>
  );
}

function CurationSkeleton() {
  return (
    <View testID="home-curation-skeleton" pointerEvents="none">
      <View style={styles.head}>
        <Skeleton width={110} height={12} radius={6} />
        <View style={styles.skeletonGap} />
        <Skeleton width={240} height={22} radius={8} />
      </View>
      <View style={styles.track}>
        {SKELETONS.map((slot) => (
          <Skeleton key={slot} width={CARD_WIDTH} height={CARD_WIDTH * 1.25} radius={16} />
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  head: { paddingHorizontal: spacing.lg },
  kick: { flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 10 },
  kickText: { fontSize: 11, fontWeight: "800", letterSpacing: 0.2, color: colors.accentText },
  kickRule: { flex: 1, height: 1, backgroundColor: colors.line },
  title: {
    fontSize: 21,
    fontWeight: "800",
    letterSpacing: -0.6,
    lineHeight: 27,
    color: colors.ink,
  },
  subtitle: {
    marginTop: 6,
    fontSize: 13,
    fontWeight: "500",
    lineHeight: 19,
    color: colors.sec,
  },
  track: {
    flexDirection: "row",
    gap: CARD_GAP,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
  },
  card: { width: CARD_WIDTH },
  imageSlot: { position: "relative" },
  image: { width: CARD_WIDTH, height: Math.round(CARD_WIDTH * 1.25) },
  badge: {
    position: "absolute",
    top: 10,
    left: 10,
    minWidth: 23,
    height: 23,
    paddingHorizontal: 8,
    borderRadius: radii.pill,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.control,
  },
  badgeText: { fontSize: 11, fontWeight: "800", color: colors.onImage },
  cardTitle: {
    marginTop: 10,
    fontSize: 15.5,
    fontWeight: "800",
    letterSpacing: -0.4,
    color: colors.ink,
  },
  cardNote: { marginTop: 2, fontSize: 12.5, fontWeight: "600", color: colors.ter },
  skeletonGap: { height: 10 },
  pressed: { opacity: 0.82 },
});
