import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Animated,
  Dimensions,
  PanResponder,
  Pressable,
  ScrollView,
  Share,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Skeleton } from "@/components/Skeleton";
import { useSpot } from "@/features/spots/queries";
import { useSaveOptimistic } from "@/features/saved/hooks/use-save-optimistic";
import { SpotHero, HeroNavButton } from "@/features/spots/components/SpotHero";
import { IntroSection } from "@/features/spots/components/IntroSection";
import { LocationSection } from "@/features/spots/components/LocationSection";
import { VisitSection } from "@/features/spots/components/VisitSection";
import { NearbyRail } from "@/features/spots/components/NearbyRail";
import { PhotoViewer } from "@/features/spots/components/PhotoViewer";
import { detailSheetSnapY, type DetailSnap } from "@/features/spots/lib/detail-sheet-snap";
import type { NearbySpot } from "@/lib/api-types";
import { colors, radii, spacing } from "@/constants/theme";

const H = Dimensions.get("window").height;
const NAV_ZONE_PX = 76;

type Snap = DetailSnap;

interface Props {
  contentId: string;
  tabBarHeight: number;
  onClose: () => void;
  seed?: NearbySpot | null;
}

export function SpotDetailSheet({ contentId, tabBarHeight, onClose, seed }: Props) {
  const { data, isLoading, isError, refetch, isPlaceholderData } = useSpot(contentId, seed);
  const { saved, toggle: onToggleSave } = useSaveOptimistic(contentId);
  const [galleryOpen, setGalleryOpen] = useState(false);
  const [snap, setSnap] = useState<Snap>("base");
  const [heroH, setHeroH] = useState<number | null>(null);

  const hasGallery = !!data && (data.images.length > 0 || !!data.firstImageUrl);
  const {
    peek: peekY,
    base: baseY,
    full: fullY,
  } = detailSheetSnapY(H, heroH, tabBarHeight, hasGallery);

  const y = useMemo(() => new Animated.Value(H), []);

  useEffect(() => {
    Animated.spring(y, {
      toValue: snap === "peek" ? peekY : snap === "base" ? baseY : fullY,
      useNativeDriver: false,
      bounciness: 2,
    }).start();
  }, [y, snap, peekY, baseY, fullY]);

  const animateClose = useCallback(() => {
    Animated.timing(y, { toValue: H, duration: 200, useNativeDriver: false }).start(
      ({ finished }) => {
        if (finished) onClose();
      },
    );
  }, [y, onClose]);

  const pan = useMemo(() => {
    const Y3: Record<Snap, number> = { peek: peekY, base: baseY, full: fullY };
    return PanResponder.create({
      onMoveShouldSetPanResponderCapture: (_e, g) => {
        if (Math.abs(g.dy) <= 10 || Math.abs(g.dy) <= Math.abs(g.dx) * 1.25) return false;
        return snap !== "full" || g.y0 < fullY + NAV_ZONE_PX;
      },
      onPanResponderGrant: () => y.stopAnimation(),
      onPanResponderTerminationRequest: () => false,
      onPanResponderTerminate: () => {
        Animated.spring(y, { toValue: Y3[snap], useNativeDriver: false, bounciness: 2 }).start();
      },
      onPanResponderMove: (_e, g) => {
        y.setValue(Math.max(fullY, Math.min(peekY, Y3[snap] + g.dy)));
      },
      onPanResponderRelease: (_e, g) => {
        const landing = Y3[snap] + g.dy;
        const next = (["full", "base", "peek"] as Snap[]).reduce((best, cand) =>
          Math.abs(Y3[cand] - landing) < Math.abs(Y3[best] - landing) ? cand : best,
        );
        setSnap(next);
        Animated.spring(y, { toValue: Y3[next], useNativeDriver: false, bounciness: 2 }).start();
      },
    });
  }, [snap, y, peekY, baseY, fullY]);

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

  return (
    <Animated.View style={[styles.sheet, { transform: [{ translateY: y }] }]} {...pan.panHandlers}>
      <View style={styles.clip}>
        <ScrollView
          scrollEnabled={snap === "full"}
          showsVerticalScrollIndicator={false}
          contentContainerStyle={{ paddingBottom: fullY + tabBarHeight + spacing.xxl }}
        >
          <SpotHero
            data={data}
            navTopPadding={26}
            onViewAll={() => {
              if (galleryImages.length > 0) setGalleryOpen(true);
            }}
            onHeroHeight={setHeroH}
            nav={
              <>
                <View />
                <View style={styles.navGroup}>
                  <HeroNavButton
                    icon={saved ? "bookmark-fill" : "bookmark"}
                    onPress={onToggleSave}
                    strokeWidth={1.8}
                  />
                  <HeroNavButton icon="close" onPress={animateClose} />
                </View>
              </>
            }
          />
          {isError && !data ? (
            <View style={styles.err}>
              <Text style={styles.errText}>불러오지 못했어요</Text>
              <Pressable style={styles.retry} onPress={() => refetch()}>
                <Text style={styles.retryText}>다시 시도</Text>
              </Pressable>
            </View>
          ) : isLoading || !data || isPlaceholderData ? (
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
        <View style={styles.grabber} pointerEvents="none" />
      </View>
      <PhotoViewer
        visible={galleryOpen}
        images={galleryImages}
        onClose={() => setGalleryOpen(false)}
      />
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  sheet: {
    position: "absolute",
    left: 0,
    right: 0,
    top: 0,
    height: H,
    shadowColor: "#100E12",
    shadowOpacity: 0.16,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: -4 },
    elevation: 12,
  },
  clip: {
    flex: 1,
    borderTopLeftRadius: radii.xl,
    borderTopRightRadius: radii.xl,
    overflow: "hidden",
    backgroundColor: colors.bg,
  },
  grabber: {
    position: "absolute",
    top: 10,
    alignSelf: "center",
    width: 40,
    height: 4,
    borderRadius: 2,
    backgroundColor: "rgba(255,255,255,0.72)",
  },
  navGroup: { flexDirection: "row", gap: 10 },
  err: {
    alignItems: "center",
    paddingVertical: spacing.xxl,
    paddingHorizontal: spacing.xl,
    gap: spacing.sm,
  },
  errText: { color: colors.sec, fontSize: 15, fontWeight: "600" },
  retry: {
    marginTop: spacing.xs,
    paddingHorizontal: 18,
    height: 38,
    borderRadius: 999,
    backgroundColor: colors.fill,
    alignItems: "center",
    justifyContent: "center",
  },
  retryText: { fontSize: 13.5, fontWeight: "700", color: colors.ink },
});
