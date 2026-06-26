import { useState } from "react";
import { ScrollView, View, Text, Pressable, Share, StyleSheet } from "react-native";
import { useLocalSearchParams, router } from "expo-router";
import { useSpot } from "@/features/spots/queries";
import { useSaveOptimistic } from "@/features/saved/hooks/use-save-optimistic";
import { Icon } from "@/components/Icon";
import { RemoteImage } from "@/components/RemoteImage";
import { Skeleton } from "@/components/Skeleton";
import { IntroSection } from "@/features/spots/components/IntroSection";
import { Gallery } from "@/features/spots/components/Gallery";
import { PhotoViewer } from "@/features/spots/components/PhotoViewer";
import { LocationSection } from "@/features/spots/components/LocationSection";
import { VisitSection } from "@/features/spots/components/VisitSection";
import { NearbyRail } from "@/features/spots/components/NearbyRail";
import { firstSentence } from "@/features/spots/lib/overview";
import { colors, spacing } from "@/constants/theme";

export default function SpotScreen() {
  const { contentId } = useLocalSearchParams<{ contentId: string }>();
  const { data, isLoading, isError, refetch } = useSpot(contentId);
  const { saved, toggle: onToggleSave } = useSaveOptimistic(contentId);
  const [galleryOpen, setGalleryOpen] = useState(false);

  const galleryImages =
    data && data.images.length > 0
      ? data.images.map((img) => img.originImageUrl ?? img.smallImageUrl).filter(Boolean)
      : data?.firstImageUrl
        ? [data.firstImageUrl]
        : [];

  const onShare = () => {
    if (!data) return;
    void Share.share({ message: `${data.title} · PicTrip` });
  };

  const onViewAll = () => {
    if (galleryImages.length > 0) setGalleryOpen(true);
  };

  const subline = data
    ? [data.category, [data.regionName, data.sigunguName].filter(Boolean).join(" ")]
        .filter(Boolean)
        .join(" · ")
    : "";
  const lead = firstSentence(data?.overview ?? null);

  if (isError && !data) {
    return (
      <View style={styles.root}>
        <View style={styles.errNav}>
          <Pressable style={styles.errBack} onPress={() => router.back()} hitSlop={6}>
            <Icon name="chevron-left" size={22} color={colors.ink} />
          </Pressable>
        </View>
        <View style={styles.errWrap}>
          <Text style={styles.errTitle}>불러오지 못했어요</Text>
          <Text style={styles.errSub}>잠시 후 다시 시도해 주세요</Text>
          <Pressable style={styles.retryBtn} onPress={() => refetch()}>
            <Text style={styles.retryText}>다시 시도</Text>
          </Pressable>
        </View>
      </View>
    );
  }

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
      <PhotoViewer
        visible={galleryOpen}
        images={galleryImages}
        onClose={() => setGalleryOpen(false)}
      />
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
  errNav: { flexDirection: "row", paddingHorizontal: 14, paddingTop: 62 },
  errBack: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.inset,
  },
  errWrap: { flex: 1, alignItems: "center", justifyContent: "center", paddingHorizontal: 44 },
  errTitle: {
    fontSize: 20,
    fontWeight: "700",
    letterSpacing: -0.36,
    marginBottom: 6,
    color: colors.ink,
  },
  errSub: { fontSize: 13, color: colors.sec, marginBottom: 26 },
  retryBtn: {
    height: 48,
    paddingHorizontal: 26,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.ink,
  },
  retryText: { fontSize: 15, fontWeight: "700", color: colors.onImage },
});
