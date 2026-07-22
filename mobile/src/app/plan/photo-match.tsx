import { useEffect, useRef, useState } from "react";
import { Image, ScrollView, View, Text, StyleSheet } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router } from "expo-router";
import { PrimaryButton } from "@/components/PrimaryButton";
import { PlanNavBar } from "@/features/plan/components/PlanNavBar";
import { PlanLoading } from "@/features/plan/components/PlanLoading";
import { PlanToast } from "@/features/plan/components/PlanToast";
import { MatchCard } from "@/features/plan/components/MatchCard";
import { usePlanDraft } from "@/features/plan/stores/plan-draft-store";
import { usePhotoMatchMutation, usePlanFromSpotMutation } from "@/features/plan/queries";
import { planErrorMessage } from "@/features/plan/lib/plan-errors";
import { colors, spacing } from "@/constants/theme";

export default function PhotoMatchScreen() {
  const { photo, matches, seedIndex, setMatches, selectSeed } = usePlanDraft();
  const match = usePhotoMatchMutation();
  const fromSpot = usePlanFromSpotMutation();
  const [toast, setToast] = useState<string | null>(null);
  const requested = useRef(false);

  useEffect(() => {
    if (!photo || requested.current) return;
    requested.current = true;
    match.mutate(photo, {
      onSuccess: setMatches,
      onError: (error) => setToast(planErrorMessage(error)),
    });
  }, [photo]); // eslint-disable-line react-hooks/exhaustive-deps

  const seed = seedIndex != null ? matches[seedIndex] : null;

  const onBuild = () => {
    if (!seed) return;
    fromSpot.mutate(
      { contentId: seed.contentId, days: 1 },
      {
        onSuccess: (plan) => {
          if (plan.planId) router.replace(`/plan/${plan.planId}`);
        },
        onError: (error) => setToast(planErrorMessage(error)),
      },
    );
  };

  const busy = match.isPending || fromSpot.isPending;

  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      <PlanNavBar title="닮은 여행지" onBack={() => router.back()} />

      {match.isPending ? (
        <PlanLoading title="사진의 분위기를 읽고 있어요" sub="비슷한 국내 여행지를 찾는 중" />
      ) : fromSpot.isPending ? (
        <PlanLoading
          title="당일 일정을 만들고 있어요"
          sub={seed ? `${seed.title} 주변을 동선으로 엮는 중` : undefined}
        />
      ) : (
        <ScrollView showsVerticalScrollIndicator={false}>
          <View style={styles.hero}>
            {photo ? <Image source={{ uri: photo.uri }} style={styles.heroImage} /> : null}
            <View style={styles.veil} />
            <View style={styles.heroCap}>
              <Text style={styles.heroTitle}>이 사진과 닮은{"\n"}여행지를 찾았어요</Text>
              <Text style={styles.heroSub}>닮은 순으로 보여드려요</Text>
            </View>
          </View>

          <View style={styles.grid}>
            {matches.map((item, index) => (
              <MatchCard
                key={item.contentId}
                match={item}
                rank={index + 1}
                selected={seedIndex === index}
                onPress={() => selectSeed(index)}
              />
            ))}
          </View>
        </ScrollView>
      )}

      {!busy && matches.length > 0 ? (
        <View style={styles.cta}>
          <PrimaryButton
            testID="plan-build-from-spot"
            label={seed ? "이곳으로 당일 일정 만들기" : "마음에 드는 곳을 골라 주세요"}
            disabled={!seed}
            onPress={onBuild}
          />
        </View>
      ) : null}

      <PlanToast message={toast} onHide={() => setToast(null)} />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  hero: { height: 198, backgroundColor: colors.ink },
  heroImage: { position: "absolute", top: 0, left: 0, right: 0, bottom: 0 },
  veil: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: "rgba(16,14,18,0.42)",
  },
  heroCap: { position: "absolute", left: spacing.lg, right: spacing.lg, bottom: 16 },
  heroTitle: {
    fontSize: 22,
    lineHeight: 30,
    fontWeight: "800",
    letterSpacing: -0.5,
    color: colors.onImage,
  },
  heroSub: { marginTop: 5, fontSize: 13, fontWeight: "600", color: colors.onDim },
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "space-between",
    rowGap: 16,
    paddingHorizontal: spacing.lg,
    paddingTop: 18,
    paddingBottom: spacing.sm,
  },
  cta: {
    paddingHorizontal: spacing.lg,
    paddingTop: 12,
    paddingBottom: 18,
    backgroundColor: colors.bg,
  },
});
