import { useCallback, useEffect, useRef, useState } from "react";
import { FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Linking } from "react-native";
import { router } from "expo-router";
import { Icon } from "@/components/Icon";
import { Toast } from "@/components/Toast";
import { AssistantTurn } from "@/features/travel/components/AssistantTurn";
import { AiConsentSheet } from "@/features/travel/components/AiConsentSheet";
import { ChatComposer } from "@/features/travel/components/ChatComposer";
import { UserBubble } from "@/features/travel/components/UserBubble";
import { WelcomeBubble } from "@/features/travel/components/WelcomeBubble";
import { useAiConsent } from "@/features/travel/hooks/use-ai-consent";
import { useKeyboardHeight } from "@/features/travel/hooks/use-keyboard-height";
import { useNearbyCoords } from "@/features/travel/hooks/use-nearby-coords";
import { AI_CONSENT } from "@/features/travel/lib/ai-consent";
import { contextFrom } from "@/features/travel/lib/conversation-context";
import { composeQuestion } from "@/features/travel/lib/question";
import {
  streamChat,
  type PhotoUpload,
  type RefinePatch,
  type TravelSpot,
} from "@/features/travel/api";
import { refineQuestion } from "@/features/travel/lib/refine-label";
import {
  historyOf,
  lastDoneTurn,
  useChat,
  type ChatRequestSeed,
  type ChatTurn,
} from "@/features/travel/stores/chat-store";
import { AppError } from "@/lib/app-error";
import { colors, spacing } from "@/constants/theme";

export const WORDMARK = "PICTRIP";
export const NEW_CHAT_LABEL = "새 대화";
const EXTERNAL_UNAVAILABLE = "이 장소는 카카오맵에서 볼 수 있어요";
const SAVE_COMPLETE = "여행지를 저장했어요";
const UNSAVE_COMPLETE = "여행지 저장을 해제했어요";
const TOAST_LIFT = 8;

export default function TravelScreen() {
  const insets = useSafeAreaInsets();
  const keyboardPx = useKeyboardHeight();
  const [toast, setToast] = useState<string | null>(null);

  const turns = useChat((s) => s.turns);
  const streaming = useChat((s) => s.streaming);

  const { coords } = useNearbyCoords();
  const coordsRef = useRef<typeof coords>(null);
  useEffect(() => {
    coordsRef.current = coords;
  }, [coords]);

  const listRef = useRef<FlatList<ChatTurn>>(null);
  const abortRef = useRef<AbortController | null>(null);
  const focusedIdRef = useRef<string | null>(null);

  const run = useCallback((id: string, seed: ChatRequestSeed) => {
    const controller = new AbortController();
    abortRef.current = controller;
    const store = useChat.getState();
    streamChat(
      {
        message: seed.message,
        photo: seed.photo,
        coords: coordsRef.current,
        clientTime: new Date().toISOString(),
        context: seed.context,
        history: seed.history,
      },
      {
        onStep: (event) => store.applyStep(id, event),
        onDelta: (text) => store.appendDelta(id, text),
        onCards: (event) => store.setCards(id, event),
        onSources: (items) => store.setSources(id, items),
        onDone: (event) => store.finish(id, event),
        onError: (event) => store.fail(id, event.code),
      },
      controller.signal,
    )
      .then(() => {
        if (controller.signal.aborted) return;
        const turn = useChat.getState().turns.find((t) => t.id === id);
        if (turn?.status === "streaming") useChat.getState().fail(id, "UNKNOWN");
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        useChat.getState().fail(id, error instanceof AppError ? error.code : "UNKNOWN");
      });
  }, []);

  const onRefine = useCallback(
    (patch: RefinePatch) => {
      const state = useChat.getState();
      if (state.streaming) return;
      const previous = lastDoneTurn(state.turns);
      if (previous?.intent == null) return;
      const label = refineQuestion(patch);
      const seed: ChatRequestSeed = {
        message: null,
        photo: null,
        context: contextFrom(previous, null),
        intent: previous.intent,
        patch,
        history: historyOf(state.turns),
      };
      const id = state.nextTurnId();
      state.begin({ id, question: label, photoUri: null, request: seed });
      focusedIdRef.current = null;
      run(id, seed);
    },
    [run],
  );

  const { granted: aiGranted, grant: grantAi } = useAiConsent();
  const [askingConsent, setAskingConsent] = useState(false);
  const pendingRef = useRef<{ text: string; photo: PhotoUpload | null } | null>(null);

  const dispatch = useCallback(
    (text: string, photo: PhotoUpload | null) => {
      const state = useChat.getState();
      if (state.streaming) return;
      const question = composeQuestion(text, photo !== null);
      if (!question) return;
      const previous = lastDoneTurn(state.turns);
      const seed: ChatRequestSeed = {
        message: text.trim() || null,
        photo,
        context: contextFrom(previous, focusedIdRef.current),
        intent: null,
        patch: null,
        history: historyOf(state.turns),
      };
      const id = state.nextTurnId();
      state.begin({ id, question, photoUri: photo?.uri ?? null, request: seed });
      focusedIdRef.current = null;
      run(id, seed);
    },
    [run],
  );

  const submit = useCallback(
    (text: string, photo: PhotoUpload | null) => {
      if (text.trim().length > 0 && !aiGranted) {
        pendingRef.current = { text, photo };
        setAskingConsent(true);
        return;
      }
      dispatch(text, photo);
    },
    [aiGranted, dispatch],
  );

  const onAgreeAi = useCallback(() => {
    void grantAi().then(() => {
      setAskingConsent(false);
      const pending = pendingRef.current;
      pendingRef.current = null;
      if (pending) dispatch(pending.text, pending.photo);
    });
  }, [grantAi, dispatch]);

  const onDeclineAi = useCallback(() => {
    pendingRef.current = null;
    setAskingConsent(false);
    setToast(AI_CONSENT.declined);
  }, []);

  const onRetry = useCallback(() => {
    const state = useChat.getState();
    if (state.streaming) return;
    const turn = state.turns[state.turns.length - 1];
    if (!turn || turn.status !== "error") return;
    state.retry(turn.id);
    run(turn.id, turn.request);
  }, [run]);

  const onNewChat = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    focusedIdRef.current = null;
    useChat.getState().clear();
  }, []);

  const openSpot = useCallback((spot: TravelSpot) => {
    if (spot.saveable === false) {
      if (spot.externalUrl) void Linking.openURL(spot.externalUrl);
      else setToast(EXTERNAL_UNAVAILABLE);
      return;
    }
    router.push(`/spots/${spot.contentId}`);
  }, []);

  const onFocusSpot = useCallback((contentId: string | null) => {
    focusedIdRef.current = contentId;
  }, []);

  const scrollToEnd = useCallback(() => {
    listRef.current?.scrollToEnd({ animated: true });
  }, []);

  const renderTurn = useCallback(
    ({ item, index }: { item: ChatTurn; index: number }) => (
      <View style={styles.turn}>
        <UserBubble question={item.question} photoUri={item.photoUri} />
        <AssistantTurn
          turn={item}
          latest={index === turns.length - 1}
          origin={coords}
          onRetry={onRetry}
          onDetail={openSpot}
          onSaveToggle={(saved) => setToast(saved ? SAVE_COMPLETE : UNSAVE_COMPLETE)}
          onNotice={(message) => setToast(message)}
          onFocusSpot={onFocusSpot}
          onRefine={onRefine}
        />
      </View>
    ),
    [turns.length, coords, onRetry, onFocusSpot, onRefine],
  );

  const bottomPad = keyboardPx;

  return (
    <View style={styles.root}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.md }]}>
        <Text style={styles.wordmark}>{WORDMARK}</Text>
        <Pressable
          testID="travel-new-chat"
          accessibilityRole="button"
          accessibilityLabel={NEW_CHAT_LABEL}
          style={({ pressed }) => [styles.newChat, pressed && styles.pressed]}
          hitSlop={8}
          onPress={onNewChat}
        >
          <Icon name="plus" size={19} color={colors.ink} strokeWidth={2} />
        </Pressable>
      </View>

      <FlatList
        ref={listRef}
        testID="travel-transcript"
        data={turns}
        keyExtractor={(turn) => turn.id}
        renderItem={renderTurn}
        ListHeaderComponent={WelcomeBubble}
        contentContainerStyle={styles.transcript}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
        onContentSizeChange={scrollToEnd}
      />

      <View style={{ paddingBottom: bottomPad }}>
        <ChatComposer streaming={streaming} onSend={submit} onNotice={setToast} />
      </View>

      <AiConsentSheet visible={askingConsent} onAgree={onAgreeAi} onDecline={onDeclineAi} />

      <Toast
        testID="travel-toast"
        message={toast}
        bottom={bottomPad + 58 + TOAST_LIFT}
        onHide={() => setToast(null)}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  header: {
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  wordmark: { fontSize: 20, fontWeight: "800", letterSpacing: -0.5, color: colors.ink },
  newChat: {
    position: "absolute",
    right: spacing.md,
    bottom: spacing.sm,
    width: 34,
    height: 34,
    borderRadius: 17,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.fill,
  },
  pressed: { opacity: 0.7 },
  turn: { gap: spacing.sm },
  transcript: { paddingTop: spacing.sm, paddingBottom: spacing.lg, gap: spacing.lg },
});
