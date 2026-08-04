import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Animated,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  View,
  Text,
  StyleSheet,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router } from "expo-router";
import { AskComposer } from "@/features/travel/components/AskComposer";
import { ConversationTurn } from "@/features/travel/components/ConversationTurn";
import { Mascot } from "@/features/travel/components/Mascot";
import { StartActions } from "@/features/travel/components/StartActions";
import { TravelToast } from "@/features/travel/components/TravelToast";
import { TravelMapSheet } from "@/features/travel/components/TravelMapSheet";
import { useNearbyCoords } from "@/features/travel/hooks/use-nearby-coords";
import { useAskAgentMutation } from "@/features/travel/queries";
import { useConversation, type Turn } from "@/features/travel/stores/conversation-store";
import {
  agentErrorMessage,
  PHOTO_PICK_FAILED,
  PHOTO_SHOOT_FAILED,
} from "@/features/travel/lib/agent-errors";
import { composeQuestion, anchorQuestion, MY_LOCATION } from "@/features/travel/lib/question";
import { composerChips, NEARBY_CHIP, type Chip } from "@/features/travel/lib/chips";
import { pickTravelPhoto, shootTravelPhoto } from "@/features/travel/usecases/pick-travel-photo";
import { placed, type PlacedSpot } from "@/features/travel/lib/spot-geo";
import type { AskInput, PhotoUpload, TravelSpot } from "@/features/travel/api";
import { colors, spacing } from "@/constants/theme";

const TOAST_BOTTOM = 150;
const GREETING_FADE_MS = 180;

export default function TravelScreen() {
  const scrollRef = useRef<ScrollView>(null);
  const nextId = useRef(0);
  const [draft, setDraft] = useState("");
  const [photo, setPhoto] = useState<PhotoUpload | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [anchorSpot, setAnchorSpot] = useState<TravelSpot | null>(null);
  const [mapTurn, setMapTurn] = useState<{ spots: PlacedSpot[]; question: string } | null>(null);

  const turns = useConversation((s) => s.turns);
  const busy = useConversation((s) => s.busy);
  const startTurn = useConversation((s) => s.start);
  const retryTurn = useConversation((s) => s.retry);
  const resolveTurn = useConversation((s) => s.resolve);
  const failTurn = useConversation((s) => s.fail);
  const clearTurns = useConversation((s) => s.clear);

  const { coords, askable: locationAskable, ask: askLocation } = useNearbyCoords();
  const ask = useAskAgentMutation();

  const empty = turns.length === 0;
  const greetFade = useMemo(() => new Animated.Value(1), []);

  useEffect(() => {
    const fade = Animated.timing(greetFade, {
      toValue: empty ? 1 : 0,
      duration: GREETING_FADE_MS,
      useNativeDriver: true,
    });
    fade.start();
    return () => fade.stop();
  }, [empty, greetFade]);

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
        if (!anchorSpot && !coords) return;
        nextId.current += 1;
        const id = `turn-${nextId.current}`;
        const anchor = anchorSpot
          ? { contentId: anchorSpot.contentId, action: chip.action }
          : { action: chip.action };
        startTurn({
          id,
          question: anchorQuestion(anchorSpot?.title ?? MY_LOCATION, chip.label),
          request: "",
          photo: null,
          anchor,
        });
        scrollToEnd();
        run(id, { anchor });
        return;
      }
      if (chip.kind === "intent") {
        nextId.current += 1;
        const id = `turn-${nextId.current}`;
        startTurn({ id, question: chip.label, request: "", photo: null, intent: chip.intent });
        scrollToEnd();
        run(id, { intent: chip.intent });
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
    [busy, submit, anchorSpot, coords, startTurn, scrollToEnd, run],
  );

  const submitDockChip = useCallback(
    (chip: Chip) => refineFrom(lastAnswered, chip),
    [refineFrom, lastAnswered],
  );

  const onNearby = useCallback(() => submit(NEARBY_CHIP.question, null), [submit]);

  const onNewChat = useCallback(() => {
    clearTurns();
    setDraft("");
    setPhoto(null);
    setAnchorSpot(null);
  }, [clearTurns]);

  const onSpotPress = useCallback((spot: TravelSpot) => {
    router.push(`/spots/${spot.contentId}`);
  }, []);

  const onOpenMap = useCallback((turn: Turn) => {
    const spots = placed(turn.answer?.spots ?? []);
    if (spots.length > 0) setMapTurn({ spots, question: turn.question });
  }, []);

  const onSpotAnchor = useCallback((spot: TravelSpot) => {
    setAnchorSpot((current) => (current?.contentId === spot.contentId ? null : spot));
  }, []);

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

  const onChangeDraft = useCallback((text: string) => {
    setDraft(text);
    if (text.trim().length > 0) setAnchorSpot(null);
  }, []);

  const attachFrom = useCallback(
    async (source: () => Promise<PhotoUpload | null>, failure: string) => {
      try {
        const picked = await source();
        if (picked) {
          setPhoto(picked);
          setAnchorSpot(null);
        }
      } catch {
        setToast(failure);
      }
    },
    [],
  );

  const onAttach = useCallback(() => attachFrom(pickTravelPhoto, PHOTO_PICK_FAILED), [attachFrom]);

  const onShoot = useCallback(() => attachFrom(shootTravelPhoto, PHOTO_SHOOT_FAILED), [attachFrom]);

  const chips = composerChips(lastAnswered?.answer?.refinements, anchorSpot, coords !== null);

  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      <View style={styles.bar}>
        <Text style={styles.wordmark}>PICTRIP</Text>
        {empty ? null : (
          <Pressable
            testID="travel-new-chat"
            accessibilityRole="button"
            style={({ pressed }) => [styles.newChat, pressed && styles.newChatPressed]}
            hitSlop={6}
            onPress={onNewChat}
          >
            <Text style={styles.newChatText}>새 대화</Text>
          </Pressable>
        )}
      </View>

      <View style={styles.stage}>
        <ScrollView
          ref={scrollRef}
          style={styles.scroll}
          contentContainerStyle={styles.body}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
          <View style={styles.talk}>
            {turns.map((turn) => (
              <ConversationTurn
                key={turn.id}
                turn={turn}
                anchorId={anchorSpot?.contentId ?? null}
                onSpotPress={onSpotPress}
                onSpotAnchor={onSpotAnchor}
                onOpenMap={onOpenMap}
                onRetry={onRetry}
                onGrow={scrollToEnd}
              />
            ))}
          </View>
        </ScrollView>

        <Animated.View
          testID="travel-greeting"
          style={[styles.greeting, { opacity: greetFade }]}
          pointerEvents="box-none"
          accessibilityElementsHidden={!empty}
          importantForAccessibility={empty ? "auto" : "no-hide-descendants"}
        >
          <Mascot floating={empty} />
          <Text style={styles.greetingText}>오늘,{"\n"}어디로 갈까요</Text>
          <View style={styles.startActions} pointerEvents={empty ? "auto" : "none"}>
            <StartActions
              onPickPhoto={() => void onAttach()}
              onAskLocation={() => void askLocation()}
              locationAskable={locationAskable}
            />
          </View>
        </Animated.View>
      </View>

      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <AskComposer
          value={draft}
          photo={photo}
          chips={chips}
          disabled={busy}
          anchorTitle={anchorSpot?.title ?? null}
          nearbyEnabled={coords !== null}
          onClearAnchor={() => setAnchorSpot(null)}
          onChange={onChangeDraft}
          onSuggest={submitDockChip}
          onNearby={onNearby}
          onAttach={() => void onAttach()}
          onShoot={() => void onShoot()}
          onClearAttach={() => setPhoto(null)}
          onSubmit={() => submit(draft, photo)}
        />
      </KeyboardAvoidingView>

      {mapTurn ? (
        <TravelMapSheet
          spots={mapTurn.spots}
          question={mapTurn.question}
          onClose={() => setMapTurn(null)}
        />
      ) : null}

      <TravelToast message={toast} bottom={TOAST_BOTTOM} onHide={() => setToast(null)} />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  bar: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    minHeight: 32,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  wordmark: { fontSize: 20, fontWeight: "800", letterSpacing: -0.5, color: colors.ink },
  newChat: {
    height: 32,
    paddingHorizontal: 13,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.line,
    justifyContent: "center",
  },
  newChatPressed: { backgroundColor: colors.fill },
  newChatText: { fontSize: 13, fontWeight: "700", letterSpacing: -0.2, color: colors.sec },
  stage: { flex: 1 },
  scroll: { flex: 1 },
  body: { paddingBottom: spacing.xxl },
  greeting: {
    position: "absolute",
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    alignItems: "center",
    justifyContent: "center",
  },
  startActions: { alignItems: "center", width: "100%", paddingHorizontal: spacing.lg },
  greetingText: {
    marginTop: 16,
    textAlign: "center",
    fontSize: 26,
    fontWeight: "800",
    letterSpacing: -0.9,
    lineHeight: 34,
    color: colors.ink,
  },
  talk: { marginTop: 22, marginHorizontal: spacing.lg },
});
