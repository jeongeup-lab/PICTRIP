import { useCallback, useRef, useState } from "react";
import { KeyboardAvoidingView, Platform, ScrollView, View, Text, StyleSheet } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router } from "expo-router";
import { useChannelCards } from "@/features/channels/queries";
import { AskComposer } from "@/features/travel/components/AskComposer";
import { PinBoard, type BoardFilter } from "@/features/travel/components/PinBoard";
import { ConversationTurn } from "@/features/travel/components/ConversationTurn";
import { TravelToast } from "@/features/travel/components/TravelToast";
import { useNearbyCoords } from "@/features/travel/hooks/use-nearby-coords";
import { useAskAgentMutation } from "@/features/travel/queries";
import { useConversation, type Turn } from "@/features/travel/stores/conversation-store";
import { channelCardsToSpots } from "@/features/travel/lib/channel-spots";
import { mergeBoardSpots } from "@/features/travel/lib/board";
import { agentErrorMessage, PHOTO_PICK_FAILED } from "@/features/travel/lib/agent-errors";
import { composeQuestion, anchorQuestion } from "@/features/travel/lib/question";
import { composerChips, type Chip } from "@/features/travel/lib/chips";
import { pickTravelPhoto } from "@/features/travel/usecases/pick-travel-photo";
import type { AskInput, PhotoUpload, TravelSpot } from "@/features/travel/api";
import { colors, spacing } from "@/constants/theme";

const NEARBY_NOTICE = "위치를 켜면 근처를 찾아드려요";
const TOAST_BOTTOM = 104;

export default function TravelScreen() {
  const scrollRef = useRef<ScrollView>(null);
  const nextId = useRef(0);
  const [draft, setDraft] = useState("");
  const [photo, setPhoto] = useState<PhotoUpload | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [filter, setFilter] = useState<BoardFilter>("all");
  const [anchorSpot, setAnchorSpot] = useState<TravelSpot | null>(null);

  const turns = useConversation((s) => s.turns);
  const busy = useConversation((s) => s.busy);
  const startTurn = useConversation((s) => s.start);
  const retryTurn = useConversation((s) => s.retry);
  const resolveTurn = useConversation((s) => s.resolve);
  const failTurn = useConversation((s) => s.fail);
  const finishPlayback = useConversation((s) => s.finishPlayback);

  const { coords, phase } = useNearbyCoords();
  const ask = useAskAgentMutation();

  const hot = useChannelCards("hot");
  const hidden = useChannelCards("hidden");
  const around = useChannelCards("around", coords ?? undefined);

  const hotSpots = channelCardsToSpots("hot", hot.data?.cards ?? []);
  const hiddenSpots = channelCardsToSpots("hidden", hidden.data?.cards ?? []);
  const aroundSpots =
    phase === "ready" ? channelCardsToSpots("around", around.data?.cards ?? []) : [];
  const boardSpots =
    filter === "all"
      ? mergeBoardSpots([hotSpots, hiddenSpots, aroundSpots]).map((spot) => ({
          ...spot,
          tag: null,
        }))
      : { hot: hotSpots, hidden: hiddenSpots, around: aroundSpots }[filter];
  const boardNotice = filter === "around" && phase !== "ready" ? NEARBY_NOTICE : null;

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
      setAnchorSpot(null);
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
      if (chip.kind === "anchor") {
        if (!anchorSpot) return;
        nextId.current += 1;
        const id = `turn-${nextId.current}`;
        const anchor = { contentId: anchorSpot.contentId, action: chip.action };
        startTurn({
          id,
          question: anchorQuestion(anchorSpot.title, chip.label),
          request: "",
          photo: null,
          anchor,
        });
        scrollToEnd();
        run(id, { anchor });
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
    [busy, submit, anchorSpot, startTurn, scrollToEnd, run],
  );

  const submitDockChip = useCallback(
    (chip: Chip) => refineFrom(lastAnswered, chip),
    [refineFrom, lastAnswered],
  );

  const onSpotPress = useCallback(
    (spot: TravelSpot) => {
      if (anchorSpot?.contentId === spot.contentId) {
        router.push(`/spots/${spot.contentId}`);
        return;
      }
      setAnchorSpot(spot);
    },
    [anchorSpot],
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
        anchor: turn.anchor,
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

  const chips = composerChips(
    lastAnswered?.answer?.refinements,
    coords !== null,
    anchorSpot !== null,
  );

  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      <View style={styles.bar}>
        <Text style={styles.wordmark}>PICTRIP</Text>
      </View>

      <ScrollView
        ref={scrollRef}
        style={styles.scroll}
        contentContainerStyle={styles.body}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
      >
        <View style={styles.lede}>
          <Text style={styles.eyebrow}>VISUAL BOARD</Text>
          <Text style={styles.headline}>오늘,{"\n"}어디로 갈까요</Text>
          <Text style={styles.sub}>사진을 모으고 질문을 더하면 닮은 국내 여행지로 이어드려요</Text>
        </View>

        <PinBoard
          filter={filter}
          spots={boardSpots}
          notice={boardNotice}
          onFilter={setFilter}
          onPhotoStart={() => void onPhotoStart()}
        />

        {turns.length > 0 ? (
          <View style={styles.talk}>
            {turns.map((turn) => (
              <ConversationTurn
                key={turn.id}
                turn={turn}
                anchorId={anchorSpot?.contentId ?? null}
                onSpotPress={onSpotPress}
                onPlaybackEnd={finishPlayback}
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
          anchorTitle={anchorSpot?.title ?? null}
          onClearAnchor={() => setAnchorSpot(null)}
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
  wordmark: { fontSize: 20, fontWeight: "800", letterSpacing: -0.5, color: colors.ink },
  scroll: { flex: 1 },
  body: { paddingBottom: spacing.xxl },
  lede: { paddingTop: spacing.xl, paddingHorizontal: spacing.lg, paddingBottom: 6 },
  eyebrow: {
    fontSize: 10.5,
    fontWeight: "900",
    letterSpacing: 1.3,
    color: colors.accentText,
  },
  headline: {
    marginTop: 7,
    fontSize: 25,
    fontWeight: "800",
    letterSpacing: -0.8,
    lineHeight: 33.5,
    color: colors.ink,
  },
  sub: { marginTop: 8, fontSize: 13, lineHeight: 19, color: colors.sec },
  talk: {
    marginTop: 30,
    marginHorizontal: spacing.lg,
    paddingTop: 22,
    borderTopWidth: 1,
    borderTopColor: colors.line,
  },
});
