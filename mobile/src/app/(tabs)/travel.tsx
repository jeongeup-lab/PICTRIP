import { useCallback, useMemo, useState } from "react";
import { ActionSheetIOS, Keyboard, StyleSheet, View, useWindowDimensions } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router } from "expo-router";
import { Toast } from "@/components/Toast";
import { KakaoWebMap } from "@/features/map/components/KakaoWebMap";
import { ChatTranscript } from "@/features/travel/components/ChatTranscript";
import { EmptyGreeting } from "@/features/travel/components/EmptyGreeting";
import { SearchPulse } from "@/features/travel/components/SearchPulse";
import { TravelDock } from "@/features/travel/components/TravelDock";
import { TravelSheet } from "@/features/travel/components/TravelSheet";
import { useNearbyCoords } from "@/features/travel/hooks/use-nearby-coords";
import { useKeyboardHeight } from "@/features/travel/hooks/use-keyboard-height";
import { useAskAgentMutation, useMoodImagesQuery } from "@/features/travel/queries";
import { useConversation, type FollowKey } from "@/features/travel/stores/conversation-store";
import {
  agentErrorMessage,
  PHOTO_PICK_FAILED,
  PHOTO_SHOOT_FAILED,
} from "@/features/travel/lib/agent-errors";
import { composeQuestion, MY_LOCATION } from "@/features/travel/lib/question";
import { contextFrom } from "@/features/travel/lib/conversation-context";
import { askedKeys, followUps, type FollowChip } from "@/features/travel/lib/follow-ups";
import { coordsOf } from "@/features/travel/lib/distance";
import { bounds, center, pinsFrom, placed } from "@/features/travel/lib/spot-geo";
import { dockBasePx, mapFitPadding } from "@/features/travel/lib/screen-layout";
import { sheetHeightPx, type SheetSnap } from "@/features/travel/lib/sheet-layout";
import { pickTravelPhoto, shootTravelPhoto } from "@/features/travel/usecases/pick-travel-photo";
import type { AskInput, PhotoUpload, TravelSpot } from "@/features/travel/api";
import { colors, spacing } from "@/constants/theme";

const SAVE_COMPLETE = "여행지를 저장했어요";
const UNSAVE_COMPLETE = "여행지 저장을 해제했어요";
const TOAST_LIFT = 12;
const NO_SPOTS: TravelSpot[] = [];

export const ATTACH_SHOOT_LABEL = "촬영";
export const ATTACH_PICK_LABEL = "앨범에서 선택";
export const ATTACH_CANCEL_LABEL = "취소";
export const LOCATION_CHECKING = "위치를 확인하는 중이에요";
export const LOCATION_REQUIRED = "위치를 켜면 내 근처를 찾아드려요";
export const ASK_PLACEHOLDER = "어디로 갈지 말해보세요";
export const ATTACHED_PLACEHOLDER = "지역이나 조건을 덧붙여 보세요";

export default function TravelScreen() {
  const insets = useSafeAreaInsets();
  const { height: frameH } = useWindowDimensions();
  const keyboardPx = useKeyboardHeight();
  const [draft, setDraft] = useState("");
  const [photo, setPhoto] = useState<PhotoUpload | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [snap, setSnap] = useState<SheetSnap>("mid");
  const [focusedAt, setFocusedAt] = useState(0);
  const [scrollToAt, setScrollToAt] = useState<number | null>(null);

  const turns = useConversation((s) => s.turns);
  const busy = useConversation((s) => s.busy);
  const startTurn = useConversation((s) => s.start);
  const retryTurn = useConversation((s) => s.retry);
  const resolveTurn = useConversation((s) => s.resolve);
  const failTurn = useConversation((s) => s.fail);
  const clearTurns = useConversation((s) => s.clear);
  const nextTurnId = useConversation((s) => s.nextTurnId);

  const {
    coords,
    phase: locationPhase,
    askable: locationAskable,
    ask: askLocation,
  } = useNearbyCoords();
  const ask = useAskAgentMutation();
  const moodImages = useMoodImagesQuery(turns.length === 0);

  const turn = turns.length > 0 ? turns[turns.length - 1] : null;
  const answer = turn?.status === "done" ? turn.answer : null;
  const spots = answer?.spots ?? NO_SPOTS;
  const focused = spots[focusedAt] ?? null;

  const mapSpots = useMemo(() => placed(spots), [spots]);
  const pins = useMemo(() => pinsFrom(mapSpots), [mapSpots]);

  const dockPx = dockBasePx({ primer: locationAskable, attached: photo !== null });
  const sheetPx =
    sheetHeightPx({
      snap,
      frameH,
      insetTop: insets.top,
      insetBottom: insets.bottom,
      keyboardPx,
      dockPx,
    }) + keyboardPx;

  const fit = useMemo(() => {
    const box = bounds(mapSpots);
    if (!box) return null;
    return { ...box, pad: mapFitPadding({ safeTop: insets.top, dockHeight: sheetPx }) };
  }, [mapSpots, insets.top, sheetPx]);

  const focus = useMemo(() => {
    if (focused) return coordsOf(focused) ?? center(mapSpots) ?? coords;
    return center(mapSpots) ?? coords;
  }, [focused, mapSpots, coords]);

  const asked = useMemo(() => askedKeys(turns), [turns]);
  const followUp = useMemo(() => {
    if (!answer) return null;
    return followUps({
      title: focused?.title ?? MY_LOCATION,
      contentId: focused?.contentId ?? null,
      asked,
      isDetailTurn: (turn?.followKey ?? null) !== null,
      refinements: answer.refinements ?? null,
      suggestions: answer.suggestions ?? null,
    });
  }, [answer, focused, asked, turn]);

  const run = useCallback(
    (id: string, input: Omit<AskInput, "coords">) => {
      ask.mutate(
        { ...input, coords },
        {
          onSuccess: (result) => {
            resolveTurn(id, result);
            setSnap("mid");
          },
          onError: (error) => failTurn(id, agentErrorMessage(error)),
        },
      );
    },
    [ask, coords, resolveTurn, failTurn],
  );

  const resetFocus = useCallback(() => {
    setFocusedAt(0);
    setScrollToAt(null);
  }, []);

  const beginTurn = useCallback(() => {
    resetFocus();
    setSnap("mid");
  }, [resetFocus]);

  const submit = useCallback(
    (text: string, attached: PhotoUpload | null, followKey: FollowKey | null = null) => {
      if (busy) return;
      const question = composeQuestion(text, attached !== null);
      if (!question) return;
      const request = text.trim();
      const id = nextTurnId();
      const context = contextFrom(answer, focused?.contentId ?? null);
      startTurn({ id, question, request, photo: attached, context, followKey });
      setDraft("");
      setPhoto(null);
      beginTurn();
      run(id, { question: request, photo: attached, context });
    },
    [busy, nextTurnId, answer, focused, startTurn, beginTurn, run],
  );

  const demandCoords = useCallback(() => {
    if (locationPhase === "checking") {
      setToast(LOCATION_CHECKING);
      return;
    }
    if (locationAskable) {
      void askLocation();
      return;
    }
    setToast(LOCATION_REQUIRED);
  }, [locationPhase, locationAskable, askLocation]);

  const attachFromAlbum = useCallback(async () => {
    try {
      const picked = await pickTravelPhoto();
      if (picked) setPhoto(picked);
    } catch {
      setToast(PHOTO_PICK_FAILED);
    }
  }, []);

  const onFollowChip = useCallback(
    (chip: FollowChip) => {
      const action = chip.action;
      if (busy) return;
      if (action.kind === "question") {
        submit(action.question, null);
        return;
      }
      if (action.kind === "detail") {
        submit(action.question, null, action.followKey);
        return;
      }
      if (action.kind === "anchor") {
        const anchor = focused
          ? { contentId: focused.contentId, action: action.action }
          : { action: action.action };
        const id = nextTurnId();
        startTurn({ id, question: action.question, request: "", photo: null, anchor });
        beginTurn();
        run(id, { anchor });
        return;
      }
      const intent = answer?.intent ?? null;
      if (!intent) return;
      if (action.patch?.nearMe === true && !coords) {
        demandCoords();
        return;
      }
      const attached = turn?.photo ?? null;
      const id = nextTurnId();
      startTurn({
        id,
        question: action.label,
        request: "",
        photo: attached,
        intent,
        patch: action.patch,
      });
      beginTurn();
      run(id, { photo: attached, intent, patch: action.patch });
    },
    [
      busy,
      submit,
      focused,
      coords,
      demandCoords,
      nextTurnId,
      startTurn,
      beginTurn,
      run,
      answer,
      turn,
    ],
  );

  const onShoot = useCallback(async () => {
    try {
      const picked = await shootTravelPhoto();
      if (picked) setPhoto(picked);
    } catch {
      setToast(PHOTO_SHOOT_FAILED);
    }
  }, []);

  const onAttach = useCallback(() => {
    ActionSheetIOS.showActionSheetWithOptions(
      {
        options: [ATTACH_SHOOT_LABEL, ATTACH_PICK_LABEL, ATTACH_CANCEL_LABEL],
        cancelButtonIndex: 2,
      },
      (choice) => {
        if (choice === 0) void onShoot();
        if (choice === 1) void attachFromAlbum();
      },
    );
  }, [onShoot, attachFromAlbum]);

  const onNewChat = useCallback(() => {
    clearTurns();
    setDraft("");
    setPhoto(null);
    resetFocus();
    setSnap("collapsed");
  }, [clearTurns, resetFocus]);

  const onMapTap = useCallback(() => {
    Keyboard.dismiss();
    setSnap("collapsed");
  }, []);

  const onRetry = useCallback(() => {
    if (busy || !turn) return;
    retryTurn(turn.id);
    beginTurn();
    run(turn.id, {
      question: turn.request,
      photo: turn.photo,
      intent: turn.intent,
      patch: turn.patch,
      anchor: turn.anchor,
      context: turn.context,
    });
  }, [busy, turn, retryTurn, beginTurn, run]);

  const onPinTap = useCallback(
    (contentId: string) => {
      const at = spots.findIndex((s) => s.contentId === contentId);
      if (at < 0) return;
      setFocusedAt(at);
      setScrollToAt(at);
    },
    [spots],
  );

  const onFocusChange = useCallback((index: number) => {
    setFocusedAt(index);
    setScrollToAt(null);
  }, []);

  const onGrabberTap = useCallback(() => {
    setSnap((current) => (current === "collapsed" ? "mid" : current === "mid" ? "full" : "mid"));
  }, []);

  const onSnapChange = useCallback((next: SheetSnap) => {
    if (next === "collapsed") Keyboard.dismiss();
    setSnap(next);
  }, []);

  const onInputFocus = useCallback(() => {
    setSnap((current) => (current === "collapsed" ? "mid" : current));
  }, []);

  const placeholder = photo
    ? ATTACHED_PLACEHOLDER
    : focused
      ? `${focused.title}에 대해 물어보기`
      : ASK_PLACEHOLDER;

  const greetingShown = turns.length === 0;

  return (
    <View style={styles.root}>
      <KakaoWebMap
        center={focus}
        fit={fit}
        pins={pins}
        anchorId={focused?.contentId ?? null}
        userLocation={coords}
        onPinTap={onPinTap}
        onBlankTap={onMapTap}
      />

      <SearchPulse active={busy} bottom={sheetPx} />

      <TravelSheet
        snap={snap}
        keyboardPx={keyboardPx}
        dockPx={dockPx}
        greeting={greetingShown}
        canReset={turns.length > 0}
        onReset={onNewChat}
        onGrabberTap={onGrabberTap}
        onSnapChange={onSnapChange}
      >
        {greetingShown ? (
          <View style={[styles.slot, styles.greeting]}>
            <EmptyGreeting moodImages={moodImages.data} onPickPhoto={onAttach} />
          </View>
        ) : (
          <View style={styles.slot}>
            <ChatTranscript
              turns={turns}
              focusedIndex={focusedAt}
              scrollToIndex={scrollToAt}
              origin={coords}
              followUp={followUp}
              busy={busy}
              onFollowChip={onFollowChip}
              onFocusChange={onFocusChange}
              onDetail={(spot) => router.push(`/spots/${spot.contentId}`)}
              onSaveToggle={(saved) => setToast(saved ? SAVE_COMPLETE : UNSAVE_COMPLETE)}
              onMetricPress={(tooltip) => {
                if (tooltip) setToast(tooltip);
              }}
              onRetry={onRetry}
            />
          </View>
        )}
        <TravelDock
          value={draft}
          photo={photo}
          disabled={busy}
          placeholder={placeholder}
          locationAskable={locationAskable}
          onChange={setDraft}
          onFocus={onInputFocus}
          onAttach={onAttach}
          onClearAttach={() => setPhoto(null)}
          onSubmit={() => submit(draft, photo)}
          onAskLocation={() => void askLocation()}
        />
      </TravelSheet>

      <Toast
        testID="travel-toast"
        message={toast}
        bottom={sheetPx + TOAST_LIFT}
        onHide={() => setToast(null)}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  slot: { flex: 1 },
  greeting: { paddingHorizontal: spacing.md, paddingTop: spacing.sm, paddingBottom: spacing.lg },
});
