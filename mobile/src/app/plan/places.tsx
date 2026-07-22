import { useMemo, useState } from "react";
import { Pressable, ScrollView, View, Text, StyleSheet } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router } from "expo-router";
import { PrimaryButton } from "@/components/PrimaryButton";
import { PlanNavBar } from "@/features/plan/components/PlanNavBar";
import { PlanLoading } from "@/features/plan/components/PlanLoading";
import { PlanToast } from "@/features/plan/components/PlanToast";
import { MissingRow, PickRow } from "@/features/plan/components/PickRow";
import { usePlanDraft } from "@/features/plan/stores/plan-draft-store";
import { useAssembleMutation } from "@/features/plan/queries";
import { splitPlaces } from "@/features/plan/lib/place-selection";
import { shortDurationLabel } from "@/features/plan/lib/plan-format";
import { planErrorMessage } from "@/features/plan/lib/plan-errors";
import { colors, spacing } from "@/constants/theme";

export default function PlacesScreen() {
  const { imported, sourceUrl, selected, days, missingOpen, toggleSelected, toggleMissing } =
    usePlanDraft();
  const assemble = useAssembleMutation();
  const [toast, setToast] = useState<string | null>(null);

  const places = useMemo(() => imported?.places ?? [], [imported]);
  const { usable, missing } = useMemo(() => splitPlaces(places), [places]);

  const onAssemble = () => {
    if (!imported || selected.length === 0) return;
    assemble.mutate(
      {
        places: selected.map((i) => places[i]),
        days,
        sourceKind: imported.sourceKind,
        sourceUrl,
        sourceTitle: imported.sourceTitle,
      },
      {
        onSuccess: (plan) => {
          if (plan.planId) router.replace(`/plan/${plan.planId}`);
        },
        onError: (error) => setToast(planErrorMessage(error)),
      },
    );
  };

  const daysNote =
    days != null
      ? `영상 기준 ${shortDurationLabel(days)} 일정으로 만들어요`
      : "장소 수에 맞춰 알맞은 일수로 나눠 드려요";

  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      <PlanNavBar title="장소 고르기" onBack={() => router.back()} />

      {assemble.isPending ? (
        <PlanLoading title="일정을 만들고 있어요" sub="동선을 계산해 하루하루 나누는 중" />
      ) : (
        <>
          <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.body}>
            <View style={styles.head}>
              <Text style={styles.title}>영상에서 {usable.length}곳을 찾았어요</Text>
              <Text style={styles.lead}>갈 곳만 남겨 주세요 · {daysNote}</Text>
            </View>

            {usable.map((index) => (
              <PickRow
                key={index}
                place={places[index]}
                selected={selected.includes(index)}
                onPress={() => toggleSelected(index)}
              />
            ))}

            {missing.length > 0 ? (
              <>
                <Pressable
                  testID="plan-missing-toggle"
                  style={styles.missBtn}
                  onPress={toggleMissing}
                >
                  <Text style={styles.missText}>
                    정보를 못 찾은 {missing.length}곳 {missingOpen ? "접기" : "보기"}
                  </Text>
                </Pressable>
                {missingOpen
                  ? missing.map((index) => <MissingRow key={index} place={places[index]} />)
                  : null}
              </>
            ) : null}
          </ScrollView>

          <View style={styles.cta}>
            <PrimaryButton
              testID="plan-assemble"
              label={
                selected.length > 0 ? `${selected.length}곳으로 일정 만들기` : "장소를 골라 주세요"
              }
              disabled={selected.length === 0}
              onPress={onAssemble}
            />
          </View>
        </>
      )}

      <PlanToast message={toast} onHide={() => setToast(null)} />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  body: { paddingHorizontal: spacing.lg, paddingBottom: spacing.lg },
  head: { paddingTop: 18, paddingBottom: 6 },
  title: { fontSize: 19, fontWeight: "800", letterSpacing: -0.4, color: colors.ink },
  lead: { marginTop: 6, fontSize: 13, lineHeight: 19, color: colors.ter },
  missBtn: { paddingTop: 14, paddingBottom: 6 },
  missText: { fontSize: 12.5, fontWeight: "700", color: colors.ter },
  cta: {
    paddingHorizontal: spacing.lg,
    paddingTop: 12,
    paddingBottom: 18,
    backgroundColor: colors.bg,
  },
});
