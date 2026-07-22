import { useMemo, useState } from "react";
import { Linking, Pressable, ScrollView, View, Text, StyleSheet } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router, useLocalSearchParams } from "expo-router";
import { PlanNavBar } from "@/features/plan/components/PlanNavBar";
import { PlanLoading } from "@/features/plan/components/PlanLoading";
import { PlanToast } from "@/features/plan/components/PlanToast";
import { PlanStat } from "@/features/plan/components/PlanStat";
import { PlanCollage } from "@/features/plan/components/PlanCollage";
import { PlanRouteMap } from "@/features/plan/components/PlanRouteMap";
import { DayChips } from "@/features/plan/components/DayChips";
import { SlotRow, TravelGap } from "@/features/plan/components/SlotRow";
import { SlotSheet } from "@/features/plan/components/SlotSheet";
import { usePlan, usePlanEditMutation } from "@/features/plan/queries";
import { planRoutePoints } from "@/features/plan/lib/plan-route-html";
import {
  collageImages,
  durationLabel,
  planTitle,
  totalSlots,
  totalTravelMinutes,
  unplacedSummary,
} from "@/features/plan/lib/plan-format";
import { planErrorMessage } from "@/features/plan/lib/plan-errors";
import { colors, spacing } from "@/constants/theme";

type SlotTarget = { day: number; slot: number };

export default function PlanTimelineScreen() {
  const { planId } = useLocalSearchParams<{ planId: string }>();
  const { data: plan, isLoading, isError, error } = usePlan(planId);
  const edit = usePlanEditMutation(planId);
  const [focusedDay, setFocusedDay] = useState<number | null>(null);
  const [target, setTarget] = useState<SlotTarget | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const shownDays = useMemo(
    () =>
      plan ? (focusedDay == null ? plan.days : plan.days.filter((d) => d.day === focusedDay)) : [],
    [plan, focusedDay],
  );
  const points = useMemo(() => (plan ? planRoutePoints(plan, focusedDay) : []), [plan, focusedDay]);

  if (isLoading) {
    return (
      <SafeAreaView style={styles.root} edges={["top"]}>
        <PlanNavBar title="일정" onBack={() => router.back()} />
        <PlanLoading title="일정을 불러오고 있어요" />
      </SafeAreaView>
    );
  }

  if (isError || !plan) {
    return (
      <SafeAreaView style={styles.root} edges={["top"]}>
        <PlanNavBar title="일정" onBack={() => router.back()} />
        <View style={styles.center}>
          <Text style={styles.dim}>{planErrorMessage(error)}</Text>
        </View>
      </SafeAreaView>
    );
  }

  const multiDay = plan.days.length > 1;
  const visits = totalSlots(plan);
  const travel = totalTravelMinutes(plan);
  const selected = target ? plan.days.find((d) => d.day === target.day)?.slots[target.slot] : null;

  const applyEdit = (payload: Parameters<typeof edit.mutate>[0], successMessage: string): void => {
    setTarget(null);
    edit.mutate(payload, {
      onSuccess: () => setToast(successMessage),
      onError: (e) => setToast(planErrorMessage(e)),
    });
  };

  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      <PlanNavBar title="일정" onBack={() => router.back()} />

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.body}>
        <View style={styles.head}>
          <Text style={styles.display}>{planTitle(plan)}</Text>
          <View style={styles.stats}>
            {multiDay ? (
              <PlanStat icon="calendar" strong={durationLabel(plan.days.length)} />
            ) : null}
            <PlanStat icon="map-pin" strong={`${visits}곳`} suffix="방문" />
            {travel > 0 ? <PlanStat icon="clock" prefix="이동" strong={`약 ${travel}분`} /> : null}
          </View>
        </View>

        <View style={styles.media}>
          <PlanCollage images={collageImages(plan)} />
          <PlanRouteMap points={points} />
        </View>

        {multiDay ? (
          <DayChips
            days={plan.days.map((d) => d.day)}
            value={focusedDay}
            onChange={setFocusedDay}
          />
        ) : (
          <View style={styles.band} />
        )}

        {shownDays.map((day) => (
          <View key={day.day} style={styles.dayBlock}>
            {multiDay ? (
              <View style={styles.dayTitle}>
                <Text style={styles.dayNumber}>Day {day.day}</Text>
                {day.regionLabel ? <Text style={styles.dayRegion}>{day.regionLabel}</Text> : null}
              </View>
            ) : (
              <View style={styles.daySpacer} />
            )}

            <View style={styles.rail}>
              {day.slots.map((slot, index) => (
                <View key={`${day.day}-${index}`}>
                  {index > 0 && slot.travelMinutesFromPrev ? (
                    <TravelGap minutes={slot.travelMinutesFromPrev} />
                  ) : null}
                  <SlotRow
                    slot={slot}
                    first={index === 0}
                    onPress={() => setTarget({ day: day.day, slot: index })}
                  />
                </View>
              ))}
            </View>
          </View>
        ))}

        {plan.unplaced.length > 0 ? (
          <View style={styles.unplaced}>
            <Text style={styles.unplacedText}>
              <Text style={styles.unplacedStrong}>일정에 넣지 못한 {plan.unplaced.length}곳</Text> —{" "}
              {unplacedSummary(plan.unplaced)}
            </Text>
          </View>
        ) : null}

        {plan.sourceUrl ? (
          <Pressable
            testID="plan-source-link"
            style={styles.source}
            onPress={() => {
              const url = plan.sourceUrl;
              if (url) Linking.openURL(url).catch(() => {});
            }}
          >
            <Text style={styles.sourceText}>
              유튜브 영상으로 만든 일정 · <Text style={styles.sourceStrong}>원본 보기</Text>
            </Text>
          </Pressable>
        ) : null}
      </ScrollView>

      {target && selected ? (
        <SlotSheet
          planId={planId}
          slot={selected}
          day={target.day}
          slotIndex={target.slot}
          onClose={() => setTarget(null)}
          onRemove={() =>
            applyEdit({ op: "remove", day: target.day, slot: target.slot }, "일정에서 뺐어요")
          }
          onReplace={(spot) => {
            if (!spot.contentId) return;
            applyEdit(
              { op: "replace", day: target.day, slot: target.slot, contentId: spot.contentId },
              `${spot.title}(으)로 바꿨어요`,
            );
          }}
        />
      ) : null}

      <PlanToast message={toast} onHide={() => setToast(null)} />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.inset },
  body: { paddingBottom: spacing.xxl },
  center: { flex: 1, alignItems: "center", justifyContent: "center", padding: spacing.xl },
  dim: { fontSize: 14.5, lineHeight: 21, color: colors.sec, textAlign: "center" },
  head: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: 16,
    backgroundColor: colors.bg,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  display: {
    fontSize: 21,
    lineHeight: 29,
    fontWeight: "800",
    letterSpacing: -0.5,
    color: colors.ink,
  },
  stats: { flexDirection: "row", flexWrap: "wrap", gap: 7, marginTop: 11 },
  media: { paddingHorizontal: spacing.lg, paddingTop: spacing.md, paddingBottom: 4 },
  band: { height: 8 },
  dayBlock: { paddingHorizontal: spacing.lg, paddingBottom: spacing.md },
  dayTitle: {
    flexDirection: "row",
    alignItems: "baseline",
    gap: 9,
    paddingTop: 16,
    paddingBottom: 4,
  },
  dayNumber: { fontSize: 19, fontWeight: "800", letterSpacing: -0.4, color: colors.ink },
  dayRegion: { fontSize: 12.5, fontWeight: "600", color: colors.ter },
  daySpacer: { height: 14 },
  rail: { marginLeft: 5, paddingLeft: 20, borderLeftWidth: 1.5, borderLeftColor: colors.skeleton },
  unplaced: {
    marginHorizontal: spacing.lg,
    marginTop: spacing.xs,
    padding: 13,
    borderRadius: 8,
    backgroundColor: colors.bg,
  },
  unplacedText: { fontSize: 12.5, lineHeight: 20, color: colors.sec },
  unplacedStrong: { fontWeight: "700", color: colors.ink },
  source: { paddingTop: 16, alignItems: "center" },
  sourceText: { fontSize: 12.5, fontWeight: "600", color: colors.ter },
  sourceStrong: { fontWeight: "700", color: colors.accentText },
});
