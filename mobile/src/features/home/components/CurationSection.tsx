import { FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import { RemoteImage } from "@/components/RemoteImage";
import { Skeleton } from "@/components/Skeleton";
import type { Curation, HomeSpotCard } from "@/features/home/api";
import { colors, radii, spacing } from "@/constants/theme";

export const CARD_WIDTH = 248;
export const RANK_CARD_WIDTH = 156;
export const CARD_GAP = 12;
export const HOT_RANKS = 3;

const SKELETONS = [0, 1];

interface Props {
  data: Curation | undefined;
  isLoading: boolean;
  onOpenSpot: (contentId: string) => void;
}

export function CurationSection({ data, isLoading, onOpenSpot }: Props) {
  if (isLoading) return <EditorialRailSkeleton testID="home-curation-skeleton" />;
  if (!data || data.items.length === 0) return null;

  return (
    <EditorialRail
      testID="home-curation"
      kicker={data.kicker}
      title={data.title}
      subtitle={data.subtitle}
      items={data.items}
      onOpenSpot={onOpenSpot}
    />
  );
}

interface RailProps {
  testID: string;
  kicker: string;
  title: string;
  subtitle: string | null;
  items: HomeSpotCard[];
  onOpenSpot: (contentId: string) => void;
  compact?: boolean;
}

export function EditorialRail({
  testID,
  kicker,
  title,
  subtitle,
  items,
  onOpenSpot,
  compact = false,
}: RailProps) {
  const width = compact ? RANK_CARD_WIDTH : CARD_WIDTH;
  return (
    <View testID={testID}>
      <View style={styles.head}>
        <View style={styles.kick}>
          <Text style={styles.kickText}>{kicker}</Text>
          <View style={styles.kickRule} />
        </View>
        <Text style={styles.title}>{title}</Text>
        {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
      </View>

      <FlatList
        horizontal
        data={items}
        keyExtractor={(card) => card.contentId}
        showsHorizontalScrollIndicator={false}
        snapToInterval={width + CARD_GAP}
        decelerationRate="fast"
        contentContainerStyle={styles.track}
        renderItem={({ item, index }) => (
          <CurationCard
            card={item}
            index={index}
            width={width}
            hot={compact}
            onPress={() => onOpenSpot(item.contentId)}
          />
        )}
      />
    </View>
  );
}

function CurationCard({
  card,
  index,
  width,
  hot,
  onPress,
}: {
  card: HomeSpotCard;
  index: number;
  width: number;
  hot: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      testID="home-curation-card"
      accessibilityRole="button"
      accessibilityLabel={`${card.title} 상세보기`}
      style={({ pressed }) => [styles.card, { width }, pressed && styles.pressed]}
      onPress={onPress}
    >
      <View style={styles.imageSlot}>
        <RemoteImage
          uri={card.imageUrl}
          style={{ width, height: Math.round(width * 1.25) }}
          radius={16}
        />
        <View style={[styles.badge, hot && index < HOT_RANKS && styles.badgeHot]}>
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

export function EditorialRailSkeleton({ testID }: { testID: string }) {
  return (
    <View testID={testID} pointerEvents="none">
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
  card: {},
  imageSlot: { position: "relative" },
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
  badgeHot: { backgroundColor: colors.accent },
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
