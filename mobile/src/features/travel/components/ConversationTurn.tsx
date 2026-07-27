import { useEffect, useMemo, useState } from "react";
import { Animated, Easing, Pressable, ScrollView, View, Text, StyleSheet } from "react-native";
import { Image } from "expo-image";
import { Icon } from "@/components/Icon";
import { SpotCard } from "@/features/travel/components/SpotCard";
import { StepList } from "@/features/travel/components/StepList";
import { AnswerBlock } from "@/features/travel/components/AnswerBlock";
import { playbackTicks, stepProgressAt } from "@/features/travel/lib/step-playback";
import { RETRY_SUGGESTION } from "@/features/travel/lib/question";
import { refineChips, type Chip } from "@/features/travel/lib/chips";
import type { Turn } from "@/features/travel/stores/conversation-store";
import { colors, spacing } from "@/constants/theme";

const RISE_MS = 320;
const RESULT_RAIL_LIMIT = 4;

const PENDING_STEP = { tool: "pending", label: "여행지를 찾는 중", badge: null };

interface Props {
  turn: Turn;
  onPlaybackEnd: (id: string) => void;
  onSuggest: (chip: Chip, source: Turn) => void;
  onOpenResults: (turn: Turn) => void;
  onRetry: (turn: Turn) => void;
  onGrow: () => void;
}

export function ConversationTurn({
  turn,
  onPlaybackEnd,
  onSuggest,
  onOpenResults,
  onRetry,
  onGrow,
}: Props) {
  const rise = useMemo(() => new Animated.Value(0), []);
  const [elapsed, setElapsed] = useState(0);
  const [voted, setVoted] = useState(false);
  const steps = turn.answer?.steps ?? [];

  useEffect(() => {
    Animated.timing(rise, {
      toValue: 1,
      duration: RISE_MS,
      easing: Easing.bezier(0.2, 0.7, 0.3, 1),
      useNativeDriver: true,
    }).start();
  }, [rise]);

  useEffect(() => {
    if (turn.status !== "playing") return;
    const timers = playbackTicks(steps.length).map((ms) =>
      setTimeout(() => {
        setElapsed(ms);
        onGrow();
      }, ms),
    );
    return () => timers.forEach(clearTimeout);
  }, [turn.status, steps.length, onGrow]);

  const progress = stepProgressAt(steps.length, elapsed);
  const settled = turn.status === "playing" && progress.finished;

  useEffect(() => {
    if (settled) onPlaybackEnd(turn.id);
  }, [settled, onPlaybackEnd, turn.id]);

  const revealed = turn.status === "done" || settled;
  const answer = turn.answer;

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
          <StepList
            steps={turn.status === "pending" ? [PENDING_STEP] : steps}
            shown={turn.status === "pending" ? 1 : revealed ? steps.length : progress.shown}
            completed={turn.status === "pending" ? 0 : revealed ? steps.length : progress.completed}
          />
        )}

        {revealed && answer ? (
          <AnswerBlock
            answer={answer.answer}
            chips={refineChips(answer.refinements)}
            onSuggest={(chip) => onSuggest(chip, turn)}
          />
        ) : null}
      </View>

      {revealed && answer && answer.spots.length > 0 ? (
        <>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.rail}
          >
            {answer.spots.slice(0, RESULT_RAIL_LIMIT).map((spot) => (
              <SpotCard key={spot.contentId} spot={spot} />
            ))}
          </ScrollView>

          <View style={styles.foot}>
            <Pressable
              testID={`turn-results-${turn.id}`}
              style={styles.link}
              hitSlop={8}
              onPress={() => onOpenResults(turn)}
            >
              <Text style={styles.linkText}>전체 {answer.spots.length}곳 보기</Text>
              <Icon name="chevron-right" size={15} color={colors.ink} strokeWidth={2} />
            </Pressable>
            <Pressable
              testID={`turn-vote-${turn.id}`}
              accessibilityLabel="도움이 됐어요"
              style={[styles.vote, voted && styles.voteOn]}
              hitSlop={8}
              onPress={() => setVoted((v) => !v)}
            >
              <Icon
                name="check"
                size={17}
                color={voted ? colors.ink : colors.ter}
                strokeWidth={2.2}
              />
            </Pressable>
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
  link: { flexDirection: "row", alignItems: "center", gap: 3 },
  linkText: { fontSize: 13.5, fontWeight: "700", letterSpacing: -0.2, color: colors.ink },
  vote: {
    width: 30,
    height: 30,
    borderRadius: 15,
    alignItems: "center",
    justifyContent: "center",
  },
  voteOn: { backgroundColor: colors.fill },
});
