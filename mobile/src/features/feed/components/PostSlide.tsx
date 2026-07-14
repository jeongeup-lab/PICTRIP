import { View, Text, Pressable, StyleSheet } from "react-native";
import Svg, { Defs, LinearGradient, Stop, Rect } from "react-native-svg";
import { router } from "expo-router";
import { RemoteImage } from "@/components/RemoteImage";
import { FramedImage } from "@/components/FramedImage";
import { Icon } from "@/components/Icon";
import { useSaveOptimistic } from "@/features/saved/hooks/use-save-optimistic";
import { prefetchSpot } from "@/features/spots/queries";
import type { MatchCard, OverseasPost } from "@/features/feed/posts-api";
import { colors } from "@/constants/theme";

export type Slide =
  | { kind: "hero"; post: OverseasPost }
  | { kind: "match"; match: MatchCard; number: number }
  | { kind: "skeleton" };

interface Props {
  slide: Slide;
  width: number;
  counter: string;
  onInfo: () => void;
  onNavigate?: () => void;
}

export function PostSlide({ slide, width, counter, onInfo, onNavigate }: Props) {
  switch (slide.kind) {
    case "hero":
      return <HeroSlide post={slide.post} width={width} counter={counter} onInfo={onInfo} />;
    case "match":
      return (
        <MatchSlide
          match={slide.match}
          number={slide.number}
          width={width}
          counter={counter}
          onNavigate={onNavigate}
        />
      );
    case "skeleton":
    default:
      return <SkeletonSlide width={width} counter={counter} />;
  }
}

function CounterPill({ counter }: { counter: string }) {
  if (!counter) return null;
  return (
    <View style={styles.counter} pointerEvents="none">
      <Text testID="post-counter" style={styles.counterText}>
        {counter}
      </Text>
    </View>
  );
}

function HeroSlide({
  post,
  width,
  counter,
  onInfo,
}: {
  post: OverseasPost;
  width: number;
  counter: string;
  onInfo: () => void;
}) {
  return (
    <View style={[styles.slide, { width }]}>
      <RemoteImage uri={post.imageUrl} withUA cropBanner={false} style={StyleSheet.absoluteFill} />
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

      <Pressable testID="credit-info" style={styles.info} onPress={onInfo} hitSlop={8}>
        <Icon name="info" size={18} color={colors.onImage} strokeWidth={1.8} />
      </Pressable>
      <CounterPill counter={counter} />

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
  counter,
  onNavigate,
}: {
  match: MatchCard;
  number: number;
  width: number;
  counter: string;
  onNavigate?: () => void;
}) {
  const { saved, toggle } = useSaveOptimistic(match.contentId);

  return (
    <Pressable
      testID="match-card"
      style={[styles.slide, { width }]}
      onPressIn={() => prefetchSpot(match.contentId)}
      onPress={() => {
        onNavigate?.();
        router.push(`/spots/${match.contentId}`);
      }}
    >
      <FramedImage uri={match.imageUrl} />
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

      <Pressable
        testID="match-save"
        style={styles.save}
        onPress={(e) => {
          e.stopPropagation();
          void toggle();
        }}
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
      <CounterPill counter={counter} />

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

function SkeletonSlide({ width, counter }: { width: number; counter: string }) {
  return (
    <View style={[styles.slide, styles.skeleton, { width }]}>
      <CounterPill counter={counter} />
    </View>
  );
}

const GLASS = {
  backgroundColor: colors.glassFill,
  borderWidth: 1,
  borderColor: colors.glassBorder,
} as const;

const styles = StyleSheet.create({
  slide: { flex: 1, backgroundColor: colors.sec, overflow: "hidden" },
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
});
