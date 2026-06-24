import { useState } from "react";
import { ScrollView, View, Text, Pressable, Linking, Share, StyleSheet } from "react-native";
import { useLocalSearchParams, router } from "expo-router";
import { useSpot } from "@/features/spots/queries";
import { useAuthGate } from "@/features/auth/hooks/use-auth-gate";
import { useIsSaved, useSaveMutation, useUnsaveMutation } from "@/features/saved/queries";
import { Icon } from "@/components/Icon";
import { RemoteImage } from "@/components/RemoteImage";
import { Skeleton } from "@/components/Skeleton";
import { IntroSection } from "@/features/spots/components/IntroSection";
import { Gallery } from "@/features/spots/components/Gallery";
import { LocationSection } from "@/features/spots/components/LocationSection";
import { VisitSection } from "@/features/spots/components/VisitSection";
import { NearbyRail } from "@/features/spots/components/NearbyRail";
import { colors, spacing } from "@/constants/theme";

/** First sentence of overview, trimmed — used as the centered hero lead. */
function firstSentence(text: string | null): string | null {
  if (!text) return null;
  const match = text.trim().match(/^[\s\S]*?[.!?。]/);
  return (match ? match[0] : text).trim() || null;
}

export default function SpotScreen() {
  const { contentId } = useLocalSearchParams<{ contentId: string }>();
  const { data, isLoading } = useSpot(contentId);
  const requireAuth = useAuthGate();
  const persisted = useIsSaved(contentId);
  const [optimistic, setOptimistic] = useState<boolean | null>(null);
  const saved = optimistic ?? persisted;
  const saveMut = useSaveMutation();
  const unsaveMut = useUnsaveMutation();

  const onToggleSave = async () => {
    if (!(await requireAuth("save"))) return;
    const next = !saved;
    setOptimistic(next);
    const rollback = () => setOptimistic(!next);
    if (next) saveMut.mutate(contentId, { onError: rollback });
    else unsaveMut.mutate(contentId, { onError: rollback });
  };

  const onShare = () => {
    if (!data) return;
    void Share.share({ message: `${data.title} · PicTrip` });
  };

  const onViewAll = () => {
    const uri = data?.images[0]?.originImageUrl ?? data?.firstImageUrl;
    if (uri) void Linking.openURL(uri).catch(() => {});
  };

  const subline = data
    ? [data.category, [data.regionName, data.sigunguName].filter(Boolean).join(" ")]
        .filter(Boolean)
        .join(" · ")
    : "";
  const lead = firstSentence(data?.overview ?? null);

  return (
    <View style={styles.root}>
      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={{ paddingBottom: 36 }}
      >
        {/* Hero */}
        <View style={styles.hero}>
          <RemoteImage uri={data?.firstImageUrl ?? null} style={StyleSheet.absoluteFill} />
          <View style={styles.scrim} pointerEvents="none" />
          <View style={styles.scrimBottom} pointerEvents="none" />

          <View style={styles.nav}>
            <Pressable style={styles.obtn} onPress={() => router.back()} hitSlop={6}>
              <Icon name="chevron-left" size={22} color={colors.onImage} />
            </Pressable>
            <Pressable style={styles.obtn} onPress={onToggleSave} hitSlop={6}>
              <Icon
                name={saved ? "bookmark-fill" : "bookmark"}
                size={22}
                color={colors.onImage}
                strokeWidth={1.8}
              />
            </Pressable>
          </View>

          {data ? (
            <>
              <Text style={styles.title}>{data.title}</Text>
              {subline ? <Text style={styles.subline}>{subline}</Text> : null}
              {lead ? <Text style={styles.desc}>{lead}</Text> : null}
              <Gallery
                images={data.images}
                firstImageUrl={data.firstImageUrl}
                onViewAll={onViewAll}
              />
            </>
          ) : (
            <View style={styles.heroSkeleton} />
          )}
        </View>

        {isLoading || !data ? (
          <View style={{ padding: spacing.lg, gap: spacing.md }}>
            <Skeleton height={18} />
            <Skeleton height={18} width="80%" />
          </View>
        ) : (
          <>
            <IntroSection overview={data.overview} />
            <LocationSection spot={data} />
            <VisitSection title={data.title} onShare={onShare} onScrap={onToggleSave} />
            <NearbyRail lat={data.mapy} lng={data.mapx} excludeId={data.contentId} />
          </>
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  hero: { backgroundColor: colors.sec, paddingBottom: 22 },
  scrim: {
    position: "absolute",
    left: 0,
    right: 0,
    top: 0,
    height: "55%",
    backgroundColor: colors.scrim,
  },
  scrimBottom: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    top: "45%",
    backgroundColor: "rgba(20,18,22,0.62)",
  },
  nav: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingHorizontal: 14,
    paddingTop: 62,
  },
  obtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.control,
  },
  title: {
    textAlign: "center",
    fontSize: 30,
    fontWeight: "800",
    letterSpacing: -0.6,
    color: colors.onImage,
    marginTop: 26,
    paddingHorizontal: 24,
  },
  subline: {
    textAlign: "center",
    color: colors.onDim,
    fontSize: 16,
    fontWeight: "600",
    marginTop: 12,
  },
  desc: {
    textAlign: "center",
    fontSize: 15,
    lineHeight: 24,
    color: colors.onImage,
    marginTop: 18,
    marginHorizontal: 26,
  },
  heroSkeleton: { height: 300 },
});
