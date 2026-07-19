import { View, Text, Pressable, StyleSheet } from "react-native";
import { Icon } from "@/components/Icon";
import { colors, radii, spacing } from "@/constants/theme";
import type { ChatAnswer, ChatBoard, ChatCondition } from "@/features/chat/types";

function fmt(n: number): string {
  return n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

function roundLabel(board: ChatBoard): string {
  if (board.phase === "converged") return "마지막 고개";
  if (board.phase === "empty") return "고개 되돌리기";
  return `${board.round}번째 고개`;
}

/** Compact one-line capsule for a past round in the thread history. */
export function BoardCapsule({ board }: { board: ChatBoard }) {
  return (
    <View style={styles.capsule}>
      <View style={styles.capsuleDot} />
      <Text style={styles.capsuleText}>
        {roundLabel(board)} · {fmt(board.poolTotal)} → {board.candidateCount}곳
      </Text>
    </View>
  );
}

interface Props {
  board: ChatBoard;
  disabled: boolean;
  onAnswer: (answer: ChatAnswer) => void;
  onRemoveCondition: (id: string) => void;
  onEscape: () => void;
}

export function ScreeningBoard({ board, disabled, onAnswer, onRemoveCondition, onEscape }: Props) {
  const ratio =
    board.poolTotal > 0 ? Math.max(0.03, Math.min(1, board.candidateCount / board.poolTotal)) : 1;
  const zero = board.candidateCount === 0;

  return (
    <View style={styles.board}>
      <Text style={styles.bl}>{roundLabel(board)} · 후보</Text>
      <View style={styles.heroRow}>
        <Text style={[styles.hero, zero && styles.heroZero]}>{board.candidateCount}곳</Text>
        <Text style={styles.heroSub}>{fmt(board.poolTotal)}곳에서</Text>
      </View>
      <View style={styles.track}>
        <View style={[styles.fill, { width: `${ratio * 100}%` }, zero && styles.fillZero]} />
      </View>

      {board.conditions.length > 0 ? (
        <View style={styles.conds}>
          {board.conditions.map((c: ChatCondition) => (
            <Pressable
              key={c.id}
              style={styles.cchip}
              disabled={disabled}
              onPress={() => onRemoveCondition(c.id)}
            >
              <Text style={[styles.cchipText, c.exclude && styles.cchipExcl]}>{c.label}</Text>
              <Icon name="close" size={11} color={colors.ter} />
            </Pressable>
          ))}
        </View>
      ) : null}

      <View style={styles.divider} />

      <Text style={styles.question}>{board.question}</Text>
      <View style={styles.answers}>
        {board.answers.map((a) => {
          const accent = a.kind === "commit" || a.kind === "skip" || a.kind === "restart";
          return (
            <Pressable
              key={a.id}
              style={styles.answerRow}
              disabled={disabled}
              onPress={() => onAnswer(a)}
            >
              <Text style={[styles.answerText, accent && styles.answerAccent]}>{a.label}</Text>
              <Icon name="chevron-right" size={15} color={colors.line} />
            </Pressable>
          );
        })}
      </View>

      <Pressable style={styles.escape} onPress={onEscape}>
        <Icon name="map-pin" size={13} color={colors.ter} />
        <Text style={styles.escapeText}>후보를 지도로 볼래</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  board: {
    backgroundColor: colors.bg,
    borderRadius: 20,
    padding: spacing.lg,
    shadowColor: "#171719",
    shadowOpacity: 0.08,
    shadowRadius: 24,
    shadowOffset: { width: 0, height: 4 },
    elevation: 3,
  },
  bl: { fontSize: 12, fontWeight: "700", color: colors.ter },
  heroRow: { flexDirection: "row", alignItems: "baseline", gap: 7, marginTop: 2 },
  hero: { fontSize: 30, fontWeight: "800", color: colors.ink, letterSpacing: -0.8 },
  heroZero: { color: colors.ter },
  heroSub: { fontSize: 13, fontWeight: "600", color: colors.ter },
  track: {
    height: 3,
    borderRadius: 2,
    backgroundColor: colors.skeleton,
    overflow: "hidden",
    marginTop: 12,
    marginBottom: 14,
  },
  fill: { height: 3, borderRadius: 2, backgroundColor: colors.accent },
  fillZero: { backgroundColor: colors.ter },
  conds: { flexDirection: "row", flexWrap: "wrap", gap: spacing.xs, marginBottom: spacing.md },
  cchip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    height: 28,
    paddingHorizontal: 10,
    borderRadius: radii.pill,
    backgroundColor: colors.inset,
  },
  cchipText: { fontSize: 12, fontWeight: "700", color: colors.ink },
  cchipExcl: { color: colors.sec, textDecorationLine: "line-through" },
  divider: { height: 1, backgroundColor: colors.line, marginBottom: spacing.md },
  question: {
    fontSize: 17,
    fontWeight: "800",
    color: colors.ink,
    letterSpacing: -0.4,
    marginBottom: spacing.sm,
  },
  answers: { gap: spacing.sm },
  answerRow: {
    height: 50,
    borderRadius: 14,
    backgroundColor: colors.inset,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.md,
  },
  answerText: { fontSize: 14.5, fontWeight: "700", color: colors.ink },
  answerAccent: { color: colors.accentText },
  escape: {
    marginTop: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "flex-end",
    gap: 5,
  },
  escapeText: { fontSize: 12, fontWeight: "700", color: colors.ter },
  capsule: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    alignSelf: "center",
    paddingHorizontal: 13,
    paddingVertical: 8,
    borderRadius: radii.md,
    backgroundColor: colors.fill,
  },
  capsuleDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: colors.ter },
  capsuleText: { fontSize: 11.5, fontWeight: "700", color: colors.ter },
});
