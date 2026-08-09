import { useRef } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import type { StyleProp, TextStyle } from "react-native";
import { Image } from "expo-image";
import { SpotCarousel } from "@/features/travel/components/SpotCarousel";
import { splitAnswer } from "@/features/travel/lib/answer-split";
import { pendingSteps } from "@/features/travel/lib/pending-steps";
import type { AnswerPart, TravelSpot } from "@/features/travel/api";
import type { FollowChip, FollowUpBlock } from "@/features/travel/lib/follow-ups";
import type { Turn } from "@/features/travel/stores/conversation-store";
import type { LatLng } from "@/features/map/lib/geo";
import { colors, radii, spacing } from "@/constants/theme";

export const FAIL_TITLE = "답변을 못 받았어요";
export const RETRY_LABEL = "다시 시도";

const noop = () => {};

interface Props {
  turns: Turn[];
  focusedIndex: number;
  scrollToIndex: number | null;
  origin: LatLng | null;
  followUp: FollowUpBlock | null;
  busy: boolean;
  onFollowChip: (chip: FollowChip) => void;
  onFocusChange: (index: number) => void;
  onDetail: (spot: TravelSpot) => void;
  onSaveToggle: (saved: boolean) => void;
  onMetricPress: (tooltip: string) => void;
  onRetry: () => void;
}

function Sentence({ parts, style }: { parts: AnswerPart[]; style: StyleProp<TextStyle> }) {
  return (
    <Text style={style}>
      {parts.map((part, index) => (
        <Text key={`${index}-${part.text}`} style={part.emphasis ? styles.emphasis : undefined}>
          {part.text}
        </Text>
      ))}
    </Text>
  );
}

function UserBubble({ turn }: { turn: Turn }) {
  return (
    <View style={styles.bubbleRow}>
      <View style={styles.bubble}>
        {turn.photo ? (
          <Image source={{ uri: turn.photo.uri }} style={styles.thumb} contentFit="cover" />
        ) : null}
        <Text style={styles.bubbleText}>{turn.question}</Text>
      </View>
    </View>
  );
}

function PendingBody({ turn }: { turn: Turn }) {
  return (
    <View testID="travel-turn-step" style={styles.step}>
      <View style={styles.spinner} />
      <Text style={styles.stepText} numberOfLines={1}>
        {pendingSteps(turn)[0]?.label ?? ""}
      </Text>
    </View>
  );
}

function FailedBody({ turn, onRetry }: { turn: Turn; onRetry: () => void }) {
  return (
    <View style={styles.failed}>
      <Text style={styles.failTitle}>{FAIL_TITLE}</Text>
      {turn.errorMessage ? <Text style={styles.rest}>{turn.errorMessage}</Text> : null}
      <View style={styles.retryRow}>
        <Pressable
          testID="travel-retry"
          accessibilityRole="button"
          style={({ pressed }) => [styles.retry, pressed && styles.pressed]}
          onPress={onRetry}
        >
          <Text style={styles.retryText}>{RETRY_LABEL}</Text>
        </Pressable>
      </View>
    </View>
  );
}

function DoneBody({
  turn,
  interactive,
  focusedIndex,
  scrollToIndex,
  origin,
  onFocusChange,
  onDetail,
  onSaveToggle,
  onMetricPress,
}: {
  turn: Turn;
  interactive: boolean;
  focusedIndex: number;
  scrollToIndex: number | null;
  origin: LatLng | null;
  onFocusChange: (index: number) => void;
  onDetail: (spot: TravelSpot) => void;
  onSaveToggle: (saved: boolean) => void;
  onMetricPress: (tooltip: string) => void;
}) {
  const answer = turn.answer;
  if (answer === null) return null;
  const { lead, rest } = splitAnswer(answer.answer);
  return (
    <View>
      <View style={styles.copy}>
        <Sentence parts={lead} style={styles.lead} />
        {rest.length > 0 ? <Sentence parts={rest} style={styles.rest} /> : null}
      </View>
      {answer.spots.length > 0 ? (
        <View testID="travel-carousel-slot" style={styles.carouselSlot}>
          <SpotCarousel
            spots={answer.spots}
            tagBasis={answer.tagBasis ?? null}
            focusedIndex={interactive ? focusedIndex : 0}
            scrollToIndex={interactive ? scrollToIndex : null}
            origin={origin}
            onFocusChange={interactive ? onFocusChange : noop}
            onDetail={onDetail}
            onSaveToggle={onSaveToggle}
            onMetricPress={onMetricPress}
          />
        </View>
      ) : null}
    </View>
  );
}

function FollowUps({
  followUp,
  busy,
  onFollowChip,
}: {
  followUp: FollowUpBlock;
  busy: boolean;
  onFollowChip: (chip: FollowChip) => void;
}) {
  return (
    <View style={styles.follow}>
      <Text style={styles.followLine}>{followUp.line}</Text>
      <View style={styles.followRow}>
        {followUp.chips.map((chip, index) => (
          <Pressable
            key={`${index}-${chip.label}`}
            testID={`travel-follow-${index}`}
            accessibilityRole="button"
            disabled={busy}
            onPress={() => onFollowChip(chip)}
            style={({ pressed }) => [
              styles.chip,
              chip.muted ? styles.chipMuted : styles.chipAccent,
              (pressed || busy) && styles.pressed,
            ]}
          >
            <Text style={chip.muted ? styles.chipMutedText : styles.chipAccentText}>
              {chip.label}
            </Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

export function ChatTranscript({
  turns,
  focusedIndex,
  scrollToIndex,
  origin,
  followUp,
  busy,
  onFollowChip,
  onFocusChange,
  onDetail,
  onSaveToggle,
  onMetricPress,
  onRetry,
}: Props) {
  const scrollRef = useRef<ScrollView>(null);
  const last = turns[turns.length - 1];

  return (
    <ScrollView
      ref={scrollRef}
      testID="travel-transcript"
      showsVerticalScrollIndicator={false}
      contentContainerStyle={styles.content}
      onContentSizeChange={() => scrollRef.current?.scrollToEnd({ animated: true })}
    >
      {turns.map((turn) => (
        <View key={turn.id} style={styles.turn}>
          <UserBubble turn={turn} />
          {turn.status === "pending" ? (
            <PendingBody turn={turn} />
          ) : turn.status === "failed" ? (
            <FailedBody turn={turn} onRetry={onRetry} />
          ) : (
            <DoneBody
              turn={turn}
              interactive={turn === last}
              focusedIndex={focusedIndex}
              scrollToIndex={scrollToIndex}
              origin={origin}
              onFocusChange={onFocusChange}
              onDetail={onDetail}
              onSaveToggle={onSaveToggle}
              onMetricPress={onMetricPress}
            />
          )}
        </View>
      ))}
      {last?.status === "done" && followUp !== null ? (
        <FollowUps followUp={followUp} busy={busy} onFollowChip={onFollowChip} />
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { paddingTop: spacing.sm, paddingBottom: spacing.lg, gap: spacing.lg },
  turn: { gap: spacing.sm },
  bubbleRow: { flexDirection: "row", justifyContent: "flex-end", paddingHorizontal: spacing.md },
  bubble: {
    maxWidth: "82%",
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingHorizontal: 14,
    paddingVertical: 9,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.fillStrong,
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    borderBottomRightRadius: 4,
    borderBottomLeftRadius: 16,
  },
  bubbleText: {
    flexShrink: 1,
    fontSize: 13.5,
    fontWeight: "600",
    letterSpacing: -0.2,
    color: colors.ink,
  },
  thumb: { width: 40, height: 40, borderRadius: 10 },
  copy: { paddingHorizontal: spacing.md },
  lead: {
    fontSize: 14.5,
    fontWeight: "700",
    lineHeight: 21,
    letterSpacing: -0.35,
    color: colors.ink,
  },
  emphasis: { color: colors.accentText },
  rest: {
    marginTop: 5,
    fontSize: 13,
    fontWeight: "600",
    lineHeight: 20,
    letterSpacing: -0.2,
    color: colors.sec,
  },
  carouselSlot: { marginTop: spacing.sm },
  step: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingHorizontal: spacing.md,
  },
  spinner: {
    width: 13,
    height: 13,
    borderRadius: 7,
    borderWidth: 2,
    borderColor: colors.line,
    borderTopColor: colors.accent,
  },
  stepText: { flex: 1, fontSize: 12.5, letterSpacing: -0.2, color: colors.sec },
  failed: {
    marginHorizontal: spacing.md,
    paddingLeft: 11,
    borderLeftWidth: 3,
    borderLeftColor: colors.accent,
  },
  failTitle: { fontSize: 13.5, fontWeight: "700", letterSpacing: -0.3, color: colors.accentText },
  retryRow: { flexDirection: "row", justifyContent: "flex-end", marginTop: 12 },
  retry: {
    height: 34,
    paddingHorizontal: 18,
    borderRadius: radii.lg,
    backgroundColor: colors.accent,
    alignItems: "center",
    justifyContent: "center",
  },
  pressed: { opacity: 0.7 },
  retryText: { fontSize: 13, fontWeight: "700", color: colors.onImage },
  follow: { paddingHorizontal: spacing.md, gap: spacing.sm },
  followLine: {
    fontSize: 13,
    fontWeight: "600",
    lineHeight: 19,
    letterSpacing: -0.2,
    color: colors.sec,
  },
  followRow: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: {
    height: 31,
    paddingHorizontal: 13,
    borderRadius: radii.pill,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  chipAccent: { borderColor: "rgba(255,59,83,0.30)", backgroundColor: colors.fill },
  chipMuted: { borderColor: colors.line, backgroundColor: colors.fill },
  chipAccentText: {
    fontSize: 12.5,
    fontWeight: "700",
    letterSpacing: -0.2,
    color: colors.accentText,
  },
  chipMutedText: { fontSize: 12.5, fontWeight: "700", letterSpacing: -0.2, color: colors.sec },
});
