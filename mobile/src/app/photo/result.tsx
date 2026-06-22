import { useMemo, useState } from "react";
import { ScrollView, View, Text, Pressable, Image, StyleSheet } from "react-native";
import { router } from "expo-router";
import { Icon } from "@/components/Icon";
import { usePhotoFlowStore } from "@/features/photo/stores/photo-flow-store";
import { ResultCard } from "@/features/photo/components/ResultCard";
import { sortMatches, type SortMode } from "@/features/photo/lib/sort-matches";
import { colors, spacing, radii } from "@/constants/theme";

export default function PhotoResultScreen() {
  const asset = usePhotoFlowStore((s) => s.asset);
  const result = usePhotoFlowStore((s) => s.result);
  const [mode, setMode] = useState<SortMode>("similarity");

  const matches = useMemo(() => result?.matches ?? [], [result]);
  const hadLocation = result?.queryHadLocation ?? false;
  const sorted = useMemo(() => sortMatches(matches, mode), [matches, mode]);

  const openSpot = (contentId: string) =>
    router.replace({ pathname: "/spots/[contentId]", params: { contentId } });

  return (
    <View style={styles.root}>
      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={{ paddingBottom: spacing.xxl }}
      >
        <View style={styles.hero}>
          {asset ? <Image source={{ uri: asset.uri }} style={styles.heroImg} /> : null}
          <View style={styles.heroScrim} pointerEvents="none" />
          <Pressable style={styles.heroBack} onPress={() => router.back()} hitSlop={8}>
            <Icon name="chevron-left" size={22} color={colors.onImage} />
          </Pressable>
          <View style={styles.heroCopy} pointerEvents="none">
            <Text style={styles.eyebrow}>내 사진과 닮은</Text>
            <Text style={styles.heroTitle}>비슷한 장소 {matches.length}곳</Text>
          </View>
        </View>

        {matches.length === 0 ? (
          <View style={styles.empty}>
            <Text style={styles.emptyTitle}>닮은 장소를 찾지 못했어요</Text>
            <Text style={styles.emptySub}>다른 사진으로 다시 시도해 보세요</Text>
            <Pressable style={styles.emptyBtn} onPress={() => router.back()}>
              <Text style={styles.emptyBtnText}>다른 사진으로</Text>
            </Pressable>
          </View>
        ) : (
          <>
            {hadLocation ? (
              <View style={styles.sortRow}>
                <Pressable
                  style={[styles.pill, mode === "similarity" ? styles.pillOn : styles.pillOff]}
                  onPress={() => setMode("similarity")}
                >
                  <Text style={mode === "similarity" ? styles.pillTextOn : styles.pillTextOff}>
                    유사도순
                  </Text>
                </Pressable>
                <Pressable
                  style={[styles.pill, mode === "distance" ? styles.pillOn : styles.pillOff]}
                  onPress={() => setMode("distance")}
                >
                  <Text style={mode === "distance" ? styles.pillTextOn : styles.pillTextOff}>
                    거리순
                  </Text>
                </Pressable>
              </View>
            ) : null}

            <View style={styles.list}>
              {sorted.map((match) => (
                <ResultCard
                  key={match.contentId}
                  match={match}
                  showDistance={hadLocation}
                  onPress={() => openSpot(match.contentId)}
                />
              ))}
            </View>
          </>
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  hero: { height: 312, backgroundColor: colors.inset },
  heroImg: { width: "100%", height: "100%" },
  heroScrim: { position: "absolute", inset: 0, backgroundColor: colors.scrim },
  heroBack: {
    position: "absolute",
    top: 54,
    left: 10,
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.control,
  },
  heroCopy: { position: "absolute", left: 22, bottom: 22 },
  eyebrow: {
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 2,
    textTransform: "uppercase",
    color: colors.onDim,
  },
  heroTitle: {
    fontSize: 27,
    fontWeight: "800",
    letterSpacing: -0.5,
    marginTop: 5,
    color: colors.onImage,
  },
  sortRow: {
    flexDirection: "row",
    gap: 7,
    paddingHorizontal: spacing.lg,
    paddingTop: 18,
    paddingBottom: 8,
  },
  pill: { paddingHorizontal: 15, paddingVertical: 8, borderRadius: radii.pill },
  pillOn: { backgroundColor: colors.ink },
  pillOff: { backgroundColor: colors.fill },
  pillTextOn: { fontSize: 13, fontWeight: "700", color: colors.onImage },
  pillTextOff: { fontSize: 13, fontWeight: "700", color: colors.sec },
  list: { gap: 14, paddingHorizontal: spacing.lg, paddingTop: 8 },
  empty: { alignItems: "center", paddingHorizontal: spacing.xl, paddingTop: 48, gap: 8 },
  emptyTitle: { fontSize: 18, fontWeight: "700", color: colors.ink },
  emptySub: { fontSize: 14, color: colors.sec, marginBottom: 12 },
  emptyBtn: {
    height: 52,
    paddingHorizontal: 24,
    borderRadius: radii.sm,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.ink,
  },
  emptyBtnText: { fontSize: 15, fontWeight: "700", color: colors.onImage },
});
