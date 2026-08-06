import { useEffect, useMemo } from "react";
import { Animated, Easing, FlatList, Pressable, View, Text, StyleSheet } from "react-native";
import { Image } from "expo-image";
import { SpotCard } from "@/features/travel/components/SpotCard";
import { StepList } from "@/features/travel/components/StepList";
import { AnswerBlock } from "@/features/travel/components/AnswerBlock";
import { TurnMap } from "@/features/travel/components/TurnMap";
import { PhotoCompare } from "@/features/travel/components/PhotoCompare";
import { placed } from "@/features/travel/lib/spot-geo";
import { pendingSteps } from "@/features/travel/lib/pending-steps";
import { RETRY_SUGGESTION } from "@/features/travel/lib/question";
import type { TravelSpot } from "@/features/travel/api";
import type { Turn } from "@/features/travel/stores/conversation-store";
import { colors, spacing } from "@/constants/theme";

const RISE_MS = 320;

interface Props {
  turn: Turn;
  anchorId: string | null;
  live: boolean;
  onSpotTap: (spot: TravelSpot) => void;
  onSpotDetail: (spot: TravelSpot) => void;
  onOpenMap: (turn: Turn) => void;
  onRetry: (turn: Turn) => void;
  onGrow: () => void;
}

export function ConversationTurn({
  turn,
  anchorId,
  live,
  onSpotTap,
  onSpotDetail,
  onOpenMap,
  onRetry,
  onGrow,
}: Props) {
  const rise = useMemo(() => new Animated.Value(0), []);
  const waiting = turn.status === "pending";
  const answer = turn.answer;
  const steps = waiting ? pendingSteps(turn) : (answer?.steps ?? []);
  const mappable = useMemo(() => placed(answer?.spots ?? []), [answer]);

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

      <View style={styles.box}>
        {turn.status === "failed" ? (
          <View>
            <Text style={styles.errorText}>{turn.errorMessage}</Text>
            <Pressable
              testID={`turn-retry-${turn.id}`}
              style={({ pressed }) => [styles.retry, pressed && styles.retryPressed]}
              onPress={() => onRetry(turn)}
            >
              <Text style={styles.retryText}>{RETRY_SUGGESTION}</Text>
            </Pressable>
          </View>
        ) : (
          <StepList steps={steps} shown={steps.length} completed={waiting ? 0 : steps.length} />
        )}

        {answer && turn.photo && answer.spots.length > 0 ? (
          <PhotoCompare photo={turn.photo} match={answer.spots[0]} />
        ) : null}

        {answer ? <AnswerBlock answer={answer.answer} /> : null}
      </View>

      {answer && answer.spots.length > 0 ? (
        <>
          {mappable.length > 0 ? (
            <TurnMap
              spots={mappable}
              live={live}
              selectedId={anchorId}
              onOpen={() => onOpenMap(turn)}
            />
          ) : null}

          <FlatList
            horizontal
            data={answer.spots}
            keyExtractor={(spot) => spot.contentId}
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.rail}
            renderItem={({ item }) => (
              <SpotCard
                spot={item}
                selected={item.contentId === anchorId}
                dimmed={anchorId !== null && item.contentId !== anchorId}
                onPress={() => onSpotTap(item)}
                onDetail={() => onSpotDetail(item)}
              />
            )}
          />

          {answer.tagBasis ? (
            <Text style={styles.basis} testID={`turn-basis-${turn.id}`}>
              {answer.tagBasis}
            </Text>
          ) : null}

          <View style={styles.foot}>
            <Text style={styles.hint}>
              카드를 한 번 탭하면 이 장소 기준으로 이어서 묻고, 두 번 탭하면 상세로 가요
            </Text>
          </View>
        </>
      ) : null}
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  turn: { marginBottom: 22 },
  askRow: { flexDirection: "row", justifyContent: "flex-end", marginBottom: 14 },
  bubble: {
    maxWidth: "80%",
    backgroundColor: colors.ink,
    borderRadius: 14,
    paddingVertical: 11,
    paddingHorizontal: 14,
  },
  shot: { width: "100%", height: 104, borderRadius: 9, marginBottom: 9 },
  askText: {
    fontSize: 14.5,
    fontWeight: "500",
    lineHeight: 21.5,
    letterSpacing: -0.2,
    color: colors.onImage,
  },
  box: {
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: 16,
    padding: spacing.md + 2,
    backgroundColor: colors.bg,
  },
  errorText: { fontSize: 13.5, lineHeight: 20, color: colors.sec },
  retry: {
    alignSelf: "flex-start",
    marginTop: 14,
    height: 34,
    paddingHorizontal: 14,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: colors.line,
    justifyContent: "center",
  },
  retryPressed: { backgroundColor: colors.fill },
  retryText: { fontSize: 13, fontWeight: "700", color: colors.sec },
  rail: { gap: 11, paddingTop: 14 },
  foot: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: 16,
  },
  basis: { marginTop: 9, fontSize: 11, letterSpacing: -0.1, color: colors.ter },
  hint: { flex: 1, fontSize: 11.5, color: colors.ter },
});
