import { useCallback, useRef, useState } from "react";
import { KeyboardAvoidingView, Platform, ScrollView, View, Text, StyleSheet } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router } from "expo-router";
import { useChannelCards } from "@/features/channels/queries";
import type { ChannelKey } from "@/features/channels/api";
import { ChannelRail } from "@/features/travel/components/ChannelRail";
import { AskComposer } from "@/features/travel/components/AskComposer";
import { PhotoStartCard } from "@/features/travel/components/PhotoStartCard";
import { ConversationTurn } from "@/features/travel/components/ConversationTurn";
import { TravelToast } from "@/features/travel/components/TravelToast";
import { useNearbyCoords } from "@/features/travel/hooks/use-nearby-coords";
import { useAskAgentMutation } from "@/features/travel/queries";
import { useConversation, type Turn } from "@/features/travel/stores/conversation-store";
import { useResults } from "@/features/travel/stores/results-store";
import { channelCardsToSpots } from "@/features/travel/lib/channel-spots";
import { agentErrorMessage, PHOTO_PICK_FAILED } from "@/features/travel/lib/agent-errors";
import { composeQuestion, resultsTitle } from "@/features/travel/lib/question";
import { composerChips, type Chip } from "@/features/travel/lib/chips";
import { pickTravelPhoto } from "@/features/travel/usecases/pick-travel-photo";
import type { AskInput, PhotoUpload, TravelSpot } from "@/features/travel/api";
import { colors, spacing } from "@/constants/theme";

const NEARBY_NOTICE = "위치를 켜면 근처를 찾아드려요";
const TOAST_BOTTOM = 104;

type TravelChannelKey = Extract<ChannelKey, "hot" | "hidden" | "around">;

const SECTIONS: { key: TravelChannelKey; title: string }[] = [
  { key: "hot", title: "인기 관광지" },
  { key: "hidden", title: "숨은 관광지" },
  { key: "around", title: "내 근처" },
];

export default function TravelScreen() {
  const scrollRef = useRef<ScrollView>(null);
  const nextId = useRef(0);
  const [draft, setDraft] = useState("");
  const [photo, setPhoto] = useState<PhotoUpload | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const turns = useConversation((s) => s.turns);
  const busy = useConversation((s) => s.busy);
  const startTurn = useConversation((s) => s.start);
  const retryTurn = useConversation((s) => s.retry);
  const resolveTurn = useConversation((s) => s.resolve);
  const failTurn = useConversation((s) => s.fail);
  const finishPlayback = useConversation((s) => s.finishPlayback);
  const openResults = useResults((s) => s.open);

  const { coords, phase } = useNearbyCoords();
  const ask = useAskAgentMutation();

  const hot = useChannelCards("hot");
  const hidden = useChannelCards("hidden");
  const around = useChannelCards("around", coords ?? undefined);
  const cardsFor = { hot, hidden, around };

  const scrollToEnd = useCallback(() => {
    requestAnimationFrame(() => scrollRef.current?.scrollToEnd({ animated: true }));
  }, []);

  const lastAnswered = [...turns].reverse().find((t) => t.status === "done" && t.answer);

  const run = useCallback(
    (id: string, input: Omit<AskInput, "coords">) => {
      ask.mutate(
        { ...input, coords },
        {
          onSuccess: (answer) => resolveTurn(id, answer),
          onError: (error) => failTurn(id, agentErrorMessage(error)),
        },
      );
    },
    [ask, coords, resolveTurn, failTurn],
  );

  const submit = useCallback(
    (text: string, attached: PhotoUpload | null) => {
      if (busy) return;
      const question = composeQuestion(text, attached !== null);
      if (!question) return;
      const request = text.trim();
      nextId.current += 1;
      const id = `turn-${nextId.current}`;
      startTurn({ id, question, request, photo: attached });
      setDraft("");
      setPhoto(null);
      scrollToEnd();
      run(id, { question: request, photo: attached });
    },
    [busy, startTurn, scrollToEnd, run],
  );

  const refineFrom = useCallback(
    (source: Turn | undefined, chip: Chip) => {
      if (busy) return;
      if (chip.kind === "question") {
        submit(chip.question, null);
        return;
      }
      const intent = source?.answer?.intent ?? null;
      if (!intent) return;
      nextId.current += 1;
      const id = `turn-${nextId.current}`;
      const attached = source?.photo ?? null;
      startTurn({
        id,
        question: chip.label,
        request: "",
        photo: attached,
        intent,
        patch: chip.patch,
      });
      scrollToEnd();
      run(id, { photo: attached, intent, patch: chip.patch });
    },
    [busy, submit, startTurn, scrollToEnd, run],
  );

  const submitDockChip = useCallback(
    (chip: Chip) => refineFrom(lastAnswered, chip),
    [refineFrom, lastAnswered],
  );

  const submitTurnChip = useCallback(
    (chip: Chip, source: Turn) => refineFrom(source, chip),
    [refineFrom],
  );

  const onRetry = useCallback(
    (turn: Turn) => {
      if (busy) return;
      retryTurn(turn.id);
      run(turn.id, {
        question: turn.request,
        photo: turn.photo,
        intent: turn.intent,
        patch: turn.patch,
      });
    },
    [busy, retryTurn, run],
  );

  const onAttach = useCallback(async () => {
    try {
      const picked = await pickTravelPhoto();
      if (picked) setPhoto(picked);
    } catch {
      setToast(PHOTO_PICK_FAILED);
    }
  }, []);

  const onPhotoStart = useCallback(async () => {
    if (busy) return;
    try {
      const picked = await pickTravelPhoto();
      if (picked) submit(draft, picked);
    } catch {
      setToast(PHOTO_PICK_FAILED);
    }
  }, [busy, draft, submit]);

  const openSpotList = useCallback(
    (title: string, spots: TravelSpot[]) => {
      openResults(title, spots);
      router.push("/travel/results");
    },
    [openResults],
  );

  const chips = composerChips(lastAnswered?.answer?.suggestions, coords !== null);

  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      <View style={styles.bar}>
        <View style={styles.wordmarkRow}>
          <Text style={styles.wordmark}>PICTRIP</Text>
          <View style={styles.wordmarkDot} />
        </View>
      </View>

      <ScrollView
        ref={scrollRef}
        style={styles.scroll}
        contentContainerStyle={styles.body}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
      >
        <View style={styles.lede}>
          <Text style={styles.headline}>오늘,{"\n"}어디로 갈까요</Text>
        </View>

        <PhotoStartCard onPress={() => void onPhotoStart()} />

        {SECTIONS.map(({ key, title }) => {
          const query = cardsFor[key];
          const spots = channelCardsToSpots(key, query.data?.cards ?? []);
          const nearbyBlocked = key === "around" && phase !== "ready";
          if (!nearbyBlocked && (query.isError || spots.length === 0)) return null;
          return (
            <ChannelRail
              key={key}
              title={title}
              spots={spots}
              notice={nearbyBlocked ? NEARBY_NOTICE : null}
              onSeeAll={() => openSpotList(title, spots)}
            />
          );
        })}

        {turns.length > 0 ? (
          <View style={styles.talk}>
            {turns.map((turn) => (
              <ConversationTurn
                key={turn.id}
                turn={turn}
                onPlaybackEnd={finishPlayback}
                onSuggest={submitTurnChip}
                onOpenResults={(t) => openSpotList(resultsTitle(t.question), t.answer?.spots ?? [])}
                onRetry={onRetry}
                onGrow={scrollToEnd}
              />
            ))}
          </View>
        ) : null}
      </ScrollView>

      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <AskComposer
          value={draft}
          photo={photo}
          chips={chips}
          disabled={busy}
          onChange={setDraft}
          onSuggest={submitDockChip}
          onAttach={() => void onAttach()}
          onClearAttach={() => setPhoto(null)}
          onSubmit={() => submit(draft, photo)}
        />
      </KeyboardAvoidingView>

      <TravelToast message={toast} bottom={TOAST_BOTTOM} onHide={() => setToast(null)} />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  bar: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    alignItems: "center",
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
  scroll: { flex: 1 },
  body: { paddingBottom: spacing.xxl },
  lede: { paddingTop: spacing.xl, paddingHorizontal: spacing.lg, paddingBottom: 6 },
  headline: {
    fontSize: 25,
    fontWeight: "800",
    letterSpacing: -0.8,
    lineHeight: 33.5,
    color: colors.ink,
  },
  talk: {
    marginTop: 30,
    marginHorizontal: spacing.lg,
    paddingTop: 22,
    borderTopWidth: 1,
    borderTopColor: colors.line,
  },
});
