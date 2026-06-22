import { useState } from "react";
import { ScrollView, View, Text, Pressable, useWindowDimensions, StyleSheet } from "react-native";
import { useLocalSearchParams, router } from "expo-router";
import { useSpot } from "@/features/spots/queries";
import { useAuthGate } from "@/features/auth/hooks/use-auth-gate";
import { useIsSaved, useSaveMutation, useUnsaveMutation } from "@/features/saved/queries";
import { Icon } from "@/components/Icon";
import { RemoteImage } from "@/components/RemoteImage";
import { CongestionChip } from "@/components/CongestionChip";
import { Skeleton } from "@/components/Skeleton";
import { IntroSection } from "@/features/spots/components/IntroSection";
import { Gallery } from "@/features/spots/components/Gallery";
import { LocationSection } from "@/features/spots/components/LocationSection";
import { NearbyRail } from "@/features/spots/components/NearbyRail";
import { colors, spacing } from "@/constants/theme";

export default function SpotScreen() {
  const { contentId } = useLocalSearchParams<{ contentId: string }>();
  const { data, isLoading } = useSpot(contentId);
  const { width } = useWindowDimensions();
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

  return (
    <View style={styles.root}>
      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={{ paddingBottom: spacing.xxl }}
      >
        <View style={{ height: width * 0.92 }}>
          <RemoteImage uri={data?.firstImageUrl ?? null} style={{ width, height: width * 0.92 }} />
          <View style={styles.heroScrim} pointerEvents="none" />
          {data ? (
            <View style={styles.heroCopy} pointerEvents="none">
              <Text style={styles.heroTitle}>{data.title}</Text>
              <View style={styles.heroMeta}>
                <Text style={styles.heroSub}>
                  {[data.category, data.sigunguName].filter(Boolean).join(" · ")}
                </Text>
                <CongestionChip level={data.congestion} />
              </View>
            </View>
          ) : null}
        </View>

        {isLoading || !data ? (
          <View style={{ padding: spacing.lg, gap: spacing.md }}>
            <Skeleton height={18} />
            <Skeleton height={18} width="80%" />
          </View>
        ) : (
          <>
            <IntroSection overview={data.overview} />
            <View style={{ marginTop: spacing.xl }}>
              <Gallery images={data.images} />
            </View>
            <LocationSection spot={data} />
            <NearbyRail lat={data.mapy} lng={data.mapx} excludeId={data.contentId} />
          </>
        )}
      </ScrollView>

      <Pressable style={[styles.navBtn, styles.back]} onPress={() => router.back()} hitSlop={8}>
        <Icon name="chevron-left" size={22} color={colors.onImage} />
      </Pressable>
      <Pressable style={[styles.navBtn, styles.save]} hitSlop={8} onPress={onToggleSave}>
        <Icon name={saved ? "heart-fill" : "heart"} size={20} color={colors.onImage} />
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  heroScrim: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    height: "60%",
    backgroundColor: colors.scrimStrong,
  },
  heroCopy: { position: "absolute", left: spacing.lg, right: spacing.lg, bottom: spacing.lg },
  heroTitle: { fontSize: 28, fontWeight: "800", letterSpacing: -0.6, color: colors.onImage },
  heroMeta: { marginTop: 8, flexDirection: "row", alignItems: "center", gap: 8 },
  heroSub: { fontSize: 14, color: colors.onDim },
  navBtn: {
    position: "absolute",
    top: 52,
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.control,
  },
  back: { left: spacing.md },
  save: { right: spacing.md },
});
