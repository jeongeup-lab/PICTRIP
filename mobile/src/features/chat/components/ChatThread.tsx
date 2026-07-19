import { useEffect, useRef } from "react";
import { FlatList, ScrollView, View, Text, ActivityIndicator, StyleSheet } from "react-native";
import { colors, spacing } from "@/constants/theme";
import { BoardCapsule, ScreeningBoard } from "@/features/chat/components/ScreeningBoard";
import { ChatSpotCard } from "@/features/chat/components/ChatSpotCard";
import { ConclusionCard } from "@/features/chat/components/ConclusionCard";
import type { ChatAnswer, ChatEntry } from "@/features/chat/types";

interface Props {
  entries: ChatEntry[];
  phase: "refining" | "converged" | "empty" | "done";
  pending: boolean;
  onAnswer: (answer: ChatAnswer) => void;
  onRemoveCondition: (id: string) => void;
  onOpenSpot: (contentId: string) => void;
  onMap: () => void;
  onRestart: () => void;
}

export function ChatThread({
  entries,
  phase,
  pending,
  onAnswer,
  onRemoveCondition,
  onOpenSpot,
  onMap,
  onRestart,
}: Props) {
  const listRef = useRef<FlatList<ChatEntry>>(null);
  useEffect(() => {
    const t = setTimeout(() => listRef.current?.scrollToEnd({ animated: true }), 90);
    return () => clearTimeout(t);
  }, [entries.length, pending]);

  let latestBoardId: string | null = null;
  for (let i = entries.length - 1; i >= 0; i -= 1) {
    if (entries[i].board) {
      latestBoardId = entries[i].id;
      break;
    }
  }

  return (
    <FlatList
      ref={listRef}
      data={entries}
      keyExtractor={(e) => e.id}
      contentContainerStyle={styles.list}
      showsVerticalScrollIndicator={false}
      renderItem={({ item }) => {
        if (item.role === "user") {
          return (
            <View style={styles.userRow}>
              <Text style={styles.userBubble}>{item.text}</Text>
            </View>
          );
        }
        if (item.role === "conclusion" && item.conclusion) {
          return (
            <ConclusionCard
              title={item.conclusion.title}
              summary={item.conclusion.summary}
              spots={item.conclusion.spots}
              onOpenSpot={onOpenSpot}
              onMap={onMap}
              onRestart={onRestart}
            />
          );
        }
        const isLatestBoard = item.id === latestBoardId && phase !== "done";
        return (
          <View style={styles.botRow}>
            {item.text ? (
              <View style={styles.bot}>
                <View style={styles.sig}>
                  <View style={styles.sigDot} />
                  <Text style={styles.sigText}>픽트립</Text>
                </View>
                <Text style={styles.botText}>{item.text}</Text>
              </View>
            ) : null}
            {item.cards && item.cards.length > 0 ? (
              <ScrollView
                horizontal
                showsHorizontalScrollIndicator={false}
                contentContainerStyle={styles.cards}
              >
                {item.cards.map((c) => (
                  <ChatSpotCard
                    key={c.contentId}
                    card={c}
                    onPress={() => onOpenSpot(c.contentId)}
                  />
                ))}
              </ScrollView>
            ) : null}
            {item.board ? (
              isLatestBoard ? (
                <ScreeningBoard
                  board={item.board}
                  disabled={pending}
                  onAnswer={onAnswer}
                  onRemoveCondition={onRemoveCondition}
                  onEscape={onMap}
                />
              ) : (
                <BoardCapsule board={item.board} />
              )
            ) : null}
          </View>
        );
      }}
      ListFooterComponent={
        pending ? (
          <View style={styles.pending}>
            <ActivityIndicator size="small" color={colors.ter} />
          </View>
        ) : null
      }
    />
  );
}

const styles = StyleSheet.create({
  list: { padding: spacing.lg, gap: 17 },
  userRow: { alignItems: "flex-end" },
  userBubble: {
    maxWidth: "80%",
    backgroundColor: colors.inset,
    color: colors.ink,
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 11,
    fontSize: 14.5,
    fontWeight: "600",
    overflow: "hidden",
  },
  botRow: { gap: spacing.md },
  bot: { gap: 5 },
  sig: { flexDirection: "row", alignItems: "center", gap: 6 },
  sigDot: { width: 7, height: 7, borderRadius: 4, backgroundColor: colors.accent },
  sigText: { fontSize: 12, fontWeight: "700", color: colors.ter },
  botText: {
    fontSize: 16.5,
    fontWeight: "700",
    color: colors.ink,
    letterSpacing: -0.3,
    lineHeight: 25,
  },
  cards: { gap: 14, paddingRight: spacing.lg },
  pending: { paddingVertical: spacing.md, alignItems: "flex-start", paddingLeft: 6 },
});
