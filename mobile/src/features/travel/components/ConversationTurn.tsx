import { useEffect, useMemo } from "react";
import { Animated, Easing, Pressable, View, Text, StyleSheet } from "react-native";
import { Image } from "expo-image";
import { ResultRow } from "@/features/travel/components/ResultRow";
import { StepList } from "@/features/travel/components/StepList";
import { AnswerBlock } from "@/features/travel/components/AnswerBlock";
import { PhotoCompare } from "@/features/travel/components/PhotoCompare";
import { pendingSteps } from "@/features/travel/lib/pending-steps";
import { spotDistanceKm } from "@/features/travel/lib/distance";
import { RETRY_SUGGESTION } from "@/features/travel/lib/question";
import type { LatLng } from "@/features/map/lib/geo";
import type { TravelSpot } from "@/features/travel/api";
import type { Turn } from "@/features/travel/stores/conversation-store";
import { colors, radii, spacing } from "@/constants/theme";

const RISE_MS = 320;

export const TAP_HINT = "한 번 탭 = 이어서 묻기 · 두 번 탭 = 상세";

export const PENDING_HINT = "지도에 후보가 먼저 찍혀요";

export const FAIL_TITLE = "답변을 못 받았어요";

export function resultHeading(count: number): string {
  return `추천 ${count}곳`;
}

interface Props {
  turn: Turn;
  anchorId: string | null;
  anchored: boolean;
  origin: LatLng | null;
  showTapHint: boolean;
  onSpotTap: (spot: TravelSpot) => void;
  onSpotDetail: (spot: TravelSpot) => void;
  onRetry: (turn: Turn) => void;
  onGrow: () => void;
  onSaveToggle: (saved: boolean) => void;
}

export function ConversationTurn({
  turn,
  anchorId,
  anchored,
  origin,
  showTapHint,
  onSpotTap,
  onSpotDetail,
  onRetry,
  onGrow,
  onSaveToggle,
}: Props) {
  const rise = useMemo(() => new Animated.Value(0), []);
  const waiting = turn.status === "pending";
  const answer = turn.answer;
  const steps = waiting ? pendingSteps(turn) : (answer?.steps ?? []);
  const spots = answer?.spots ?? [];
  const holdsAnchor = spots.some((s) => s.contentId === anchorId);
  const distances = spots.map((spot) => spotDistanceKm(spot, origin));

  useEffect(() => {
    Animated.timing(rise, {
      toValue: 1,
      duration: RISE_MS,
      easing: Easing.bezier(0.2, 0.7, 0.3, 1),
      useNativeDriver: true,
    }).start();
  }, [rise]);

  useEffect(() => {
    if (turn.status === "done") onGrow();
  }, [turn.status, onGrow]);

  return (
    <Animated.View
      testID={`turn-${turn.id}`}
      style={[
        styles.turn,
        {
          opacity: rise,
          transform: [
            { translateY: rise.interpolate({ inputRange: [0, 1], outputRange: [9, 0] }) },
          ],
        },
      ]}
    >
      <View style={styles.askRow}>
        <View style={styles.bubble}>
          {turn.photo ? (
            <Image source={{ uri: turn.photo.uri }} style={styles.shot} contentFit="cover" />
          ) : null}
          <Text style={styles.askText}>{turn.question}</Text>
        </View>
      </View>

      {turn.status === "failed" ? (
        <View style={styles.failBox}>
          <Text style={styles.failTitle}>{FAIL_TITLE}</Text>
          <Text style={styles.failText}>{turn.errorMessage}</Text>
          <Pressable
            testID={`turn-retry-${turn.id}`}
            accessibilityRole="button"
            style={({ pressed }) => [styles.retry, pressed && styles.pressed]}
            onPress={() => onRetry(turn)}
          >
            <Text style={styles.retryText}>{RETRY_SUGGESTION}</Text>
          </Pressable>
        </View>
      ) : (
        <View style={styles.trace}>
          <StepList steps={steps} shown={steps.length} completed={waiting ? 0 : steps.length} />
        </View>
      )}

      {waiting ? <Text style={styles.pendingHint}>{PENDING_HINT}</Text> : null}

      {answer && turn.photo && spots.length > 0 ? (
        <View style={styles.inset}>
          <PhotoCompare photo={turn.photo} match={spots[0]} />
        </View>
      ) : null}

      {answer ? (
        <View style={styles.inset}>
          <AnswerBlock answer={answer.answer} />
        </View>
      ) : null}

      {spots.length > 0 ? (
        <>
          <View style={styles.sectionHead}>
            <Text style={styles.section}>{resultHeading(spots.length)}</Text>
            {answer?.tagBasis ? (
              <Text style={styles.basis} testID={`turn-basis-${turn.id}`}>
                {answer.tagBasis}
              </Text>
            ) : null}
            {showTapHint ? <Text style={styles.basis}>{TAP_HINT}</Text> : null}
          </View>

          {spots.map((spot, index) => (
            <ResultRow
              key={spot.contentId}
              spot={spot}
              index={index}
              first={index === 0}
              tone={anchored ? "result" : "neutral"}
              selected={holdsAnchor && spot.contentId === anchorId}
              dimmed={holdsAnchor && spot.contentId !== anchorId}
              distanceKm={distances[index]}
              onPress={() => onSpotTap(spot)}
              onDetail={() => onSpotDetail(spot)}
              onSaveToggle={onSaveToggle}
            />
          ))}
        </>
      ) : null}
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  turn: { paddingBottom: 22 },
  askRow: { flexDirection: "row", justifyContent: "flex-end", paddingHorizontal: spacing.md },
  bubble: {
    maxWidth: "78%",
    backgroundColor: colors.accent,
    borderRadius: 17,
    borderBottomRightRadius: 5,
    paddingVertical: 10,
    paddingHorizontal: 14,
  },
  shot: { width: "100%", height: 104, borderRadius: 9, marginBottom: 9 },
  askText: {
    fontSize: 14,
    fontWeight: "600",
    lineHeight: 21,
    letterSpacing: -0.2,
    color: colors.onImage,
  },
  trace: {
    marginTop: 14,
    marginHorizontal: spacing.md,
    paddingHorizontal: 13,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.raise,
  },
  inset: { marginHorizontal: spacing.md },
  pendingHint: { marginTop: 12, marginHorizontal: spacing.lg, fontSize: 12, color: colors.ter },
  failBox: {
    marginTop: 14,
    marginHorizontal: spacing.md,
    padding: 15,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.raise,
  },
  failTitle: { fontSize: 15, fontWeight: "700", letterSpacing: -0.3, color: colors.ink },
  failText: { marginTop: 7, fontSize: 13, lineHeight: 20, color: colors.sec },
  retry: {
    marginTop: 13,
    height: 40,
    borderRadius: radii.lg,
    backgroundColor: colors.accent,
    alignItems: "center",
    justifyContent: "center",
  },
  pressed: { opacity: 0.7 },
  retryText: { fontSize: 13.5, fontWeight: "700", color: colors.onImage },
  sectionHead: { paddingTop: 18, paddingHorizontal: spacing.lg, paddingBottom: 6, gap: 3 },
  section: {
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 1.1,
    color: colors.ter,
  },
  basis: { fontSize: 11.5, letterSpacing: -0.1, color: colors.ter },
});
