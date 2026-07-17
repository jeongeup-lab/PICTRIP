import { useState } from "react";
import { ScrollView, View, Text, Pressable, Share, StyleSheet } from "react-native";
import { useLocalSearchParams, router } from "expo-router";
import { useSpot } from "@/features/spots/queries";
import { useSaveOptimistic } from "@/features/saved/hooks/use-save-optimistic";
import { Icon } from "@/components/Icon";
import { Skeleton } from "@/components/Skeleton";
import { IntroSection } from "@/features/spots/components/IntroSection";
import { SpotHero, HeroNavButton } from "@/features/spots/components/SpotHero";
import { PhotoViewer } from "@/features/spots/components/PhotoViewer";
import { LocationSection } from "@/features/spots/components/LocationSection";
import { VisitSection } from "@/features/spots/components/VisitSection";
import { NearbyRail } from "@/features/spots/components/NearbyRail";
import { colors, spacing } from "@/constants/theme";

export default function SpotScreen() {
  const { contentId } = useLocalSearchParams<{ contentId: string }>();
  const { data, isLoading, isError, refetch, isPlaceholderData } = useSpot(contentId);
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
        <SpotHero
          data={data}
          navTopPadding={62}
          onViewAll={onViewAll}
          nav={
            <>
              <HeroNavButton icon="chevron-left" onPress={() => router.back()} />
              <HeroNavButton
                icon={saved ? "bookmark-fill" : "bookmark"}
                onPress={onToggleSave}
                strokeWidth={1.8}
              />
            </>
          }
        />

        {isLoading || !data || isPlaceholderData ? (
          <View style={{ padding: spacing.lg, gap: spacing.md }}>
            <Skeleton height={18} />
            <Skeleton height={18} width="80%" />
          </View>
        ) : (
          <>
            <IntroSection overview={data.overview} />
            <View style={styles.band} />
            <LocationSection spot={data} />
            <VisitSection title={data.title} onShare={onShare} onScrap={onToggleSave} />
          </>
        )}

        <NearbyRail
          lat={data?.mapy ?? null}
          lng={data?.mapx ?? null}
          excludeId={data?.contentId ?? ""}
        />
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
  band: {
    height: 8,
    backgroundColor: colors.inset,
    borderTopWidth: 1,
    borderBottomWidth: 1,
    borderColor: colors.fill,
    marginTop: 22,
  },
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
