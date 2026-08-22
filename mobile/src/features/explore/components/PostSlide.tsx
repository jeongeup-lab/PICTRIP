import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import Svg, { Defs, LinearGradient, Rect, Stop } from "react-native-svg";
import { RemoteImage } from "@/components/RemoteImage";
import { Skeleton } from "@/components/Skeleton";
import { CreditSheet } from "@/features/explore/components/CreditSheet";
import { useMatches } from "@/features/explore/queries";
import type { MatchCard, OverseasPost } from "@/features/explore/api";
import { commonsWidthFor } from "@/lib/commons-width";
import { darkColors, spacing } from "@/constants/theme";

export const MATCH_SLOTS = [0, 1, 2];

interface Props {
  post: OverseasPost;
  width: number;
  height: number;
  active: boolean;
  onOpenSpot: (contentId: string) => void;
}

export function PostSlide({ post, width, height, active, onOpenSpot }: Props) {
  const [creditOpen, setCreditOpen] = useState(false);
  const { data, isPending } = useMatches(post.id, { enabled: active });
  const matches = data?.matches ?? [];
  const credit = [post.imageAuthor?.replace(/^Author:\s*/, ""), post.imageLicense]
    .filter(Boolean)
    .join(" · ");

  return (
    <View testID="explore-slide" style={{ width, height }}>
      <RemoteImage
        uri={post.imageUrl}
        withUA
        cropBanner={false}
        commonsWidth={commonsWidthFor(width)}
        style={StyleSheet.absoluteFill}
      />

      <Svg style={StyleSheet.absoluteFill} width="100%" height="100%" pointerEvents="none">
        <Defs>
          <LinearGradient id="slideScrim" x1="0" y1="0" x2="0" y2="1">
            <Stop offset="0" stopColor="#080A0D" stopOpacity={0.62} />
            <Stop offset="0.24" stopColor="#080A0D" stopOpacity={0.06} />
            <Stop offset="0.52" stopColor="#080A0D" stopOpacity={0.16} />
            <Stop offset="1" stopColor="#080A0D" stopOpacity={0.95} />
          </LinearGradient>
        </Defs>
        <Rect x="0" y="0" width="100%" height="100%" fill="url(#slideScrim)" />
      </Svg>

      <View style={styles.panel}>
        <View style={styles.country}>
          <Text style={styles.countryText}>
            {post.countryCode} · {post.countryNameKo}
          </Text>
        </View>

        <Text style={styles.title} numberOfLines={2}>
          {post.nameKo}
        </Text>

        {post.descriptionKo ? (
          <Text style={styles.desc} numberOfLines={2}>
            {post.descriptionKo}
          </Text>
        ) : null}

        <View style={styles.matches}>
          {matches.length > 0
            ? matches
                .slice(0, 3)
                .map((match) => (
                  <MatchTile key={match.contentId} match={match} onPress={onOpenSpot} />
                ))
            : MATCH_SLOTS.map((slot) => (
                <View key={slot} testID="explore-match-skeleton" style={styles.match}>
                  <Skeleton width="100%" height={82} radius={12} />
                </View>
              ))}
        </View>

        {matches.length === 0 && !isPending && active ? (
          <Text testID="explore-match-empty" style={styles.empty}>
            지금은 닮은 국내 여행지를 찾지 못했어요
          </Text>
        ) : null}
      </View>

      <Pressable
        testID="explore-credit"
        accessibilityRole="link"
        accessibilityLabel="사진 저작권 정보"
        hitSlop={8}
        style={styles.creditRow}
        onPress={() => setCreditOpen(true)}
      >
        <Text style={styles.creditText} numberOfLines={1}>
          {credit ? `© ${credit} · ` : ""}Wikimedia Commons
        </Text>
      </Pressable>

      <CreditSheet visible={creditOpen} post={post} onClose={() => setCreditOpen(false)} />
    </View>
  );
}

function MatchTile({ match, onPress }: { match: MatchCard; onPress: (contentId: string) => void }) {
  return (
    <Pressable
      testID={`explore-match-${match.contentId}`}
      accessibilityRole="button"
      accessibilityLabel={`${match.title} 상세보기`}
      style={({ pressed }) => [styles.match, styles.matchCard, pressed && styles.pressed]}
      onPress={() => onPress(match.contentId)}
    >
      <RemoteImage uri={match.imageUrl} style={styles.matchImage} midSize />
      <View style={styles.matchCopy}>
        <Text style={styles.matchTitle} numberOfLines={1}>
          {match.title}
        </Text>
        <Text style={styles.matchRegion} numberOfLines={1}>
          {match.regionLabel}
        </Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  panel: { position: "absolute", left: spacing.lg, right: spacing.lg, bottom: 34 },
  country: {
    alignSelf: "flex-start",
    height: 22,
    paddingHorizontal: 8,
    borderRadius: 6,
    justifyContent: "center",
    backgroundColor: "rgba(255,255,255,0.16)",
  },
  countryText: { fontSize: 11, fontWeight: "700", letterSpacing: 0.3, color: darkColors.ink },
  title: {
    marginTop: 8,
    fontSize: 22,
    fontWeight: "800",
    letterSpacing: -0.6,
    color: darkColors.onImage,
  },
  desc: {
    marginTop: 4,
    fontSize: 12.5,
    lineHeight: 18,
    color: "rgba(255,255,255,0.66)",
  },
  matches: { flexDirection: "row", gap: 8, marginTop: 15 },
  match: { flex: 1, minWidth: 0 },
  matchCard: {
    borderRadius: 12,
    overflow: "hidden",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.13)",
    backgroundColor: "rgba(255,255,255,0.09)",
  },
  matchImage: { width: "100%", height: 62 },
  matchCopy: { paddingHorizontal: 8, paddingTop: 7, paddingBottom: 8 },
  matchTitle: { fontSize: 11.5, fontWeight: "700", letterSpacing: -0.2, color: darkColors.onImage },
  matchRegion: { marginTop: 1, fontSize: 10, fontWeight: "600", color: "rgba(255,255,255,0.5)" },
  empty: { marginTop: 10, fontSize: 12, fontWeight: "600", color: "rgba(255,255,255,0.6)" },
  creditRow: { position: "absolute", left: spacing.lg, right: spacing.lg, bottom: 12 },
  creditText: { fontSize: 9.5, color: "rgba(255,255,255,0.44)" },
  pressed: { opacity: 0.72 },
});
