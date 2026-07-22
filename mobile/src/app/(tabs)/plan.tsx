import { useCallback, useState } from "react";
import { ScrollView, View, Text, StyleSheet } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router } from "expo-router";
import { StartCard } from "@/features/plan/components/StartCard";
import { RecentPlanCard } from "@/features/plan/components/RecentPlanCard";
import { PlanToast } from "@/features/plan/components/PlanToast";
import { usePlanDraft } from "@/features/plan/stores/plan-draft-store";
import { useRecentPlans } from "@/features/plan/stores/recent-plans-store";
import { pickPlanPhoto } from "@/features/plan/usecases/pick-plan-photo";
import { colors, shadows, spacing } from "@/constants/theme";

export default function PlanScreen() {
  const plans = useRecentPlans((s) => s.plans);
  const startPhotoFlow = usePlanDraft((s) => s.startPhotoFlow);
  const [toast, setToast] = useState<string | null>(null);

  const onStartPhoto = useCallback(async () => {
    try {
      const photo = await pickPlanPhoto();
      if (!photo) return;
      startPhotoFlow(photo);
      router.push("/plan/photo-match");
    } catch {
      setToast("사진을 불러오지 못했어요. 사진 접근 권한을 확인해 주세요.");
    }
  }, [startPhotoFlow]);

  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      <View style={styles.bar}>
        <View style={styles.wordmarkRow}>
          <Text style={styles.wordmark}>PICTRIP</Text>
          <View style={styles.wordmarkDot} />
        </View>
      </View>

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.body}>
        <StartCard
          icon="photo"
          title="사진으로 시작"
          caption="닮은 국내 여행지를 찾아드려요"
          testID="plan-start-photo"
          onPress={() => void onStartPhoto()}
        />
        <StartCard
          icon="video"
          title="영상으로 시작"
          caption="링크만 붙여넣으면 일정이 완성돼요"
          accent
          testID="plan-start-video"
          onPress={() => router.push("/plan/from-video")}
        />

        <View style={styles.section}>
          <View style={styles.sectionHead}>
            <Text style={styles.sectionTitle}>내 일정</Text>
            {plans.length > 0 ? <Text style={styles.count}>{plans.length}</Text> : null}
          </View>

          {plans.length > 0 ? (
            <View style={styles.grid}>
              {plans.map((plan) => (
                <RecentPlanCard
                  key={plan.id}
                  plan={plan}
                  onPress={() => router.push(`/plan/${plan.id}`)}
                />
              ))}
            </View>
          ) : (
            <View style={styles.empty}>
              <Text style={styles.emptyText}>
                아직 만든 일정이 없어요.{"\n"}사진이나 영상으로 첫 일정을 만들어 보세요.
              </Text>
            </View>
          )}
        </View>
      </ScrollView>

      <PlanToast message={toast} onHide={() => setToast(null)} />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.inset },
  bar: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    alignItems: "center",
    backgroundColor: colors.bg,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  wordmarkRow: { flexDirection: "row", alignItems: "flex-end" },
  wordmark: { fontSize: 20, fontWeight: "800", letterSpacing: -0.5, color: colors.ink },
  wordmarkDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    marginLeft: 3,
    marginBottom: 4,
    backgroundColor: colors.accent,
  },
  body: { paddingHorizontal: spacing.lg, paddingTop: 12, paddingBottom: spacing.xxl },
  section: {
    marginTop: 28,
    backgroundColor: colors.bg,
    borderRadius: 16,
    padding: spacing.md,
    ...shadows.card,
  },
  sectionHead: { flexDirection: "row", alignItems: "baseline", gap: 8 },
  sectionTitle: { fontSize: 19, fontWeight: "800", letterSpacing: -0.4, color: colors.ink },
  count: { fontSize: 14, fontWeight: "800", color: colors.accentText },
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "space-between",
    rowGap: 12,
    marginTop: 12,
  },
  empty: { paddingTop: 30, paddingBottom: 14, alignItems: "center" },
  emptyText: { fontSize: 13, lineHeight: 21, color: colors.ter, textAlign: "center" },
});
