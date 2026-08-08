import { View, Text, Pressable, StyleSheet } from "react-native";
import Svg, { Defs, LinearGradient, Stop, Rect } from "react-native-svg";
import { router } from "expo-router";
import { RemoteImage } from "@/components/RemoteImage";
import { Icon } from "@/components/Icon";
import { prefetchSpot } from "@/features/spots/queries";
import type { MatchCard, OverseasPost } from "@/features/feed/posts-api";
import { commonsWidthFor } from "@/lib/commons-width";
import { colors, spacing } from "@/constants/theme";

export type Slide =
  | { kind: "hero"; post: OverseasPost }
  | { kind: "match"; match: MatchCard; number: number }
  | { kind: "empty" }
  | { kind: "skeleton" };

export const MATCH_EMPTY_TEXT = "닮은 국내 관광지를 아직 찾지 못했어요";

interface Props {
  slide: Slide;
  width: number;
  onNavigate?: () => void;
}

export function PostSlide({ slide, width, onNavigate }: Props) {
  switch (slide.kind) {
    case "hero":
      return <HeroSlide post={slide.post} width={width} />;
    case "match":
      return (
        <MatchSlide
          match={slide.match}
          number={slide.number}
          width={width}
          onNavigate={onNavigate}
        />
      );
    case "empty":
      return <EmptySlide width={width} />;
    case "skeleton":
    default:
      return <SkeletonSlide width={width} />;
  }
}

function HeroSlide({ post, width }: { post: OverseasPost; width: number }) {
  return (
    <View style={[styles.slide, { width }]}>
      <RemoteImage
        uri={post.imageUrl}
        withUA
        cropBanner={false}
        commonsWidth={commonsWidthFor(width)}
        style={StyleSheet.absoluteFill}
      />
      <Svg style={StyleSheet.absoluteFill} width="100%" height="100%" pointerEvents="none">
        <Defs>
          <LinearGradient id="postScrim" x1="0" y1="0" x2="0" y2="1">
            <Stop offset="0" stopColor="#141216" stopOpacity={0.42} />
            <Stop offset="0.42" stopColor="#141216" stopOpacity={0} />
            <Stop offset="0.68" stopColor="#141216" stopOpacity={0.18} />
            <Stop offset="1" stopColor="#141216" stopOpacity={0.72} />
          </LinearGradient>
        </Defs>
        <Rect x="0" y="0" width="100%" height="100%" fill="url(#postScrim)" />
      </Svg>

      <View style={styles.heroMeta}>
        <Text style={styles.heroName}>{post.nameKo}</Text>
        <View style={styles.heroChipRow}>
          <View style={styles.divider} />
          <Text style={styles.country}>{post.countryNameKo}</Text>
        </View>
        {post.descriptionKo ? (
          <Text style={styles.heroDesc} numberOfLines={2}>
            {post.descriptionKo}
          </Text>
        ) : null}
      </View>
    </View>
  );
}

function MatchSlide({
  match,
  number,
  width,
  onNavigate,
}: {
  match: MatchCard;
  number: number;
  width: number;
  onNavigate?: () => void;
}) {
  return (
    <Pressable
      testID="match-card"
      style={[styles.slide, { width }]}
      onPressIn={() => prefetchSpot(match)}
      onPress={() => {
        onNavigate?.();
        router.push(`/spots/${match.contentId}`);
      }}
    >
      <RemoteImage uri={match.imageUrl} style={StyleSheet.absoluteFill} />
      <Svg style={StyleSheet.absoluteFill} width="100%" height="100%" pointerEvents="none">
        <Defs>
          <LinearGradient id="matchScrim" x1="0" y1="0" x2="0" y2="1">
            <Stop offset="0" stopColor="#141216" stopOpacity={0.28} />
            <Stop offset="0.5" stopColor="#141216" stopOpacity={0.05} />
            <Stop offset="1" stopColor="#141216" stopOpacity={0.78} />
          </LinearGradient>
        </Defs>
        <Rect x="0" y="0" width="100%" height="100%" fill="url(#matchScrim)" />
      </Svg>

      <View style={styles.matchMeta}>
        <View style={styles.matchTitleRow}>
          <Text testID="match-number" style={styles.matchNumber}>
            {number}
          </Text>
          <Text style={styles.matchName}>{match.title}</Text>
        </View>
        <View style={styles.matchChip}>
          <Text style={styles.matchChipText}>{match.regionLabel}</Text>
        </View>
        {match.overviewFirst ? (
          <Text style={styles.matchOverview} numberOfLines={2}>
            {match.overviewFirst}
          </Text>
        ) : null}
      </View>
    </Pressable>
  );
}

function EmptySlide({ width }: { width: number }) {
  return (
    <View testID="match-empty" style={[styles.slide, styles.empty, { width }]}>
      <Icon name="search" size={22} color={colors.ter} strokeWidth={1.8} />
      <Text style={styles.emptyText}>{MATCH_EMPTY_TEXT}</Text>
    </View>
  );
}

function SkeletonSlide({ width }: { width: number }) {
  return <View style={[styles.slide, styles.skeleton, { width }]} />;
}

const GLASS = {
  backgroundColor: colors.glassFill,
  borderWidth: 1,
  borderColor: colors.glassBorder,
} as const;

const styles = StyleSheet.create({
  slide: { flex: 1, backgroundColor: colors.sec, overflow: "hidden" },
  heroMeta: { position: "absolute", left: 20, right: 20, bottom: 22 },
  heroName: { fontSize: 24, fontWeight: "800", letterSpacing: -0.5, color: colors.onImage },
  heroChipRow: { flexDirection: "row", alignItems: "center", gap: 8, marginTop: 8 },
  divider: { width: 1, height: 13, backgroundColor: colors.onDim },
  country: { fontSize: 13, fontWeight: "600", color: colors.onDim },
  heroDesc: { fontSize: 14.5, lineHeight: 21, color: colors.onImage, marginTop: 10 },
  matchMeta: { position: "absolute", left: 20, right: 20, bottom: 22 },
  matchTitleRow: { flexDirection: "row", alignItems: "flex-start", gap: 7 },
  matchNumber: { fontSize: 15, fontWeight: "800", color: colors.onDim, top: -7 },
  matchName: { fontSize: 22, fontWeight: "800", letterSpacing: -0.4, color: colors.onImage },
  matchChip: {
    alignSelf: "flex-start",
    marginTop: 8,
    height: 26,
    paddingHorizontal: 11,
    borderRadius: 13,
    justifyContent: "center",
    ...GLASS,
  },
  matchChipText: { fontSize: 12.5, fontWeight: "600", color: colors.onImage },
  matchOverview: { fontSize: 14, lineHeight: 20, color: colors.onDim, marginTop: 10 },
  skeleton: { backgroundColor: colors.skeleton },
  empty: {
    backgroundColor: colors.skeleton,
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.md,
    paddingHorizontal: spacing.xl,
  },
  emptyText: { fontSize: 14.5, lineHeight: 21, color: colors.sec, textAlign: "center" },
});
