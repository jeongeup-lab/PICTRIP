import { useCallback, useEffect, useMemo, useState } from "react";
import { View, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router } from "expo-router";
import { Toast } from "@/components/Toast";
import { KakaoWebMap } from "@/features/map/components/KakaoWebMap";
import { AnswerBar } from "@/features/travel/components/AnswerBar";
import {
  SpotCarousel,
  SpotCarouselSkeleton,
  CAROUSEL_BLOCK_PX,
} from "@/features/travel/components/SpotCarousel";
import { TravelDock } from "@/features/travel/components/TravelDock";
import { SearchPulse } from "@/features/travel/components/SearchPulse";
import { useNearbyCoords } from "@/features/travel/hooks/use-nearby-coords";
import { useAskAgentMutation } from "@/features/travel/queries";
import { useConversation } from "@/features/travel/stores/conversation-store";
import { useTravelAnchor } from "@/features/travel/stores/anchor-store";
import {
  agentErrorMessage,
  PHOTO_PICK_FAILED,
  PHOTO_SHOOT_FAILED,
} from "@/features/travel/lib/agent-errors";
import { composeQuestion, anchorQuestion, MY_LOCATION } from "@/features/travel/lib/question";
import { contextFrom } from "@/features/travel/lib/conversation-context";
import { dockChips, type DockChip } from "@/features/travel/lib/dock-chips";
import { pendingSteps } from "@/features/travel/lib/pending-steps";
import { coordsOf } from "@/features/travel/lib/distance";
import { bounds, center, pinsFrom, placed } from "@/features/travel/lib/spot-geo";
import { dockBasePx, mapFitPadding } from "@/features/travel/lib/screen-layout";
import { pickTravelPhoto, shootTravelPhoto } from "@/features/travel/usecases/pick-travel-photo";
import type { AskInput, PhotoUpload, TravelSpot } from "@/features/travel/api";
import { colors } from "@/constants/theme";

const SAVE_COMPLETE = "여행지를 저장했어요";
const UNSAVE_COMPLETE = "여행지 저장을 해제했어요";
const TOAST_LIFT = 12;
const NO_SPOTS: TravelSpot[] = [];

export const ASK_PLACEHOLDER = "어디로 갈지 말해보세요";
export const ATTACHED_PLACEHOLDER = "지역이나 조건을 덧붙여 보세요";

export default function TravelScreen() {
  const insets = useSafeAreaInsets();
  const [draft, setDraft] = useState("");
  const [photo, setPhoto] = useState<PhotoUpload | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [expandedAnswer, setExpandedAnswer] = useState(false);
  const [expandedChips, setExpandedChips] = useState(false);
  const [focusedIndexRaw, setFocusedIndexRaw] = useState(0);
  const [scrollToRaw, setScrollToRaw] = useState<number | null>(null);

  const turns = useConversation((s) => s.turns);
  const busy = useConversation((s) => s.busy);
  const startTurn = useConversation((s) => s.start);
  const retryTurn = useConversation((s) => s.retry);
  const resolveTurn = useConversation((s) => s.resolve);
  const failTurn = useConversation((s) => s.fail);
  const clearTurns = useConversation((s) => s.clear);
  const nextTurnId = useConversation((s) => s.nextTurnId);

  const seeded = useTravelAnchor((s) => s.spot);
  const clearSeed = useTravelAnchor((s) => s.clear);

  const { coords, askable: locationAskable, ask: askLocation } = useNearbyCoords();
  const ask = useAskAgentMutation();

  const lastTurn = turns.length > 0 ? turns[turns.length - 1] : null;
  const turn = seeded ? null : lastTurn;
  const answer = turn?.status === "done" ? turn.answer : null;
  const seededSpots = useMemo(() => (seeded ? [seeded] : NO_SPOTS), [seeded]);
  const spots = seeded ? seededSpots : (answer?.spots ?? NO_SPOTS);
  const focusedAt = seeded ? 0 : focusedIndexRaw;
  const scrollToAt = seeded ? null : scrollToRaw;
  const focused = spots[focusedAt] ?? null;
  const pending = turn?.status === "pending";

  const mapSpots = useMemo(() => placed(spots), [spots]);
  const pins = useMemo(() => pinsFrom(mapSpots), [mapSpots]);

  const dockBase = dockBasePx({ primer: locationAskable, attached: photo !== null });
  const carouselShown = pending || spots.length > 0;
  const dockHeight = dockBase + (carouselShown ? CAROUSEL_BLOCK_PX : 0);

  const fit = useMemo(() => {
    const box = bounds(mapSpots);
    if (!box) return null;
    return { ...box, pad: mapFitPadding({ safeTop: insets.top, dockHeight }) };
  }, [mapSpots, insets.top, dockHeight]);

  const focus = useMemo(() => {
    if (focused) return coordsOf(focused) ?? center(mapSpots) ?? coords;
    return center(mapSpots) ?? coords;
  }, [focused, mapSpots, coords]);

  useEffect(() => {
    if (seeded) clearTurns();
  }, [seeded, clearTurns]);

  const run = useCallback(
    (id: string, input: Omit<AskInput, "coords">) => {
      ask.mutate(
        { ...input, coords },
        {
          onSuccess: (result) => resolveTurn(id, result),
          onError: (error) => failTurn(id, agentErrorMessage(error)),
        },
      );
    },
    [ask, coords, resolveTurn, failTurn],
  );

  const beginTurn = useCallback(() => {
    clearSeed();
    setExpandedAnswer(false);
    setExpandedChips(false);
    setFocusedIndexRaw(0);
    setScrollToRaw(null);
  }, [clearSeed]);

  const submit = useCallback(
    (text: string, attached: PhotoUpload | null) => {
      if (busy) return;
      const question = composeQuestion(text, attached !== null);
      if (!question) return;
      const request = text.trim();
      const id = nextTurnId();
      const context = contextFrom(answer, focused?.contentId ?? null);
      startTurn({ id, question, request, photo: attached, context });
      setDraft("");
      setPhoto(null);
      beginTurn();
      run(id, { question: request, photo: attached, context });
    },
    [busy, nextTurnId, answer, focused, startTurn, beginTurn, run],
  );

  const onChipPress = useCallback(
    async (chip: DockChip) => {
      if (busy) return;
      if (chip.kind === "photo") {
        try {
          const picked = await pickTravelPhoto();
          if (picked) setPhoto(picked);
        } catch {
          setToast(PHOTO_PICK_FAILED);
        }
        return;
      }
      if (chip.kind === "context") {
        setExpandedChips((open) => !open);
        return;
      }
      const inner = chip.chip;
      if (inner.kind === "question") {
        submit(inner.question, null);
        return;
      }
      if (inner.kind === "anchor") {
        if (!focused && !coords) return;
        const anchor = focused
          ? { contentId: focused.contentId, action: inner.action }
          : { action: inner.action };
        const id = nextTurnId();
        startTurn({
          id,
          question: anchorQuestion(focused?.title ?? MY_LOCATION, inner.label),
          request: "",
          photo: null,
          anchor,
        });
        beginTurn();
        run(id, { anchor });
        return;
      }
      if (inner.kind === "intent") {
        const id = nextTurnId();
        startTurn({ id, question: inner.label, request: "", photo: null, intent: inner.intent });
        beginTurn();
        run(id, { intent: inner.intent });
        return;
      }
      const intent = answer?.intent ?? null;
      if (!intent) return;
      const attached = turn?.photo ?? null;
      const id = nextTurnId();
      startTurn({
        id,
        question: inner.label,
        request: "",
        photo: attached,
        intent,
        patch: inner.patch,
      });
      beginTurn();
      run(id, { photo: attached, intent, patch: inner.patch });
    },
    [busy, submit, nextTurnId, focused, coords, answer, turn, startTurn, beginTurn, run],
  );

  const onShoot = useCallback(async () => {
    try {
      const picked = await shootTravelPhoto();
      if (picked) setPhoto(picked);
    } catch {
      setToast(PHOTO_SHOOT_FAILED);
    }
  }, []);

  const onNewChat = useCallback(() => {
    clearTurns();
    setDraft("");
    setPhoto(null);
    beginTurn();
  }, [clearTurns, beginTurn]);

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
      setFocusedIndexRaw(at);
      setScrollToRaw(at);
    },
    [spots],
  );

  const onFocusChange = useCallback((index: number) => {
    setFocusedIndexRaw(index);
    setExpandedChips(false);
    setScrollToRaw(null);
  }, []);

  const chips = dockChips({
    answer,
    focused,
    expanded: expandedChips,
    hasCoords: coords !== null,
    hasCrowd: focused?.hasCrowd === true,
  });

  const placeholder = photo
    ? ATTACHED_PLACEHOLDER
    : focused
      ? `${focused.title}에 대해 물어보기`
      : ASK_PLACEHOLDER;

  const step = pending && turn ? (pendingSteps(turn)[0]?.label ?? null) : null;

  return (
    <View style={styles.root}>
      <KakaoWebMap
        center={focus}
        fit={fit}
        pins={pins}
        anchorId={focused?.contentId ?? null}
        userLocation={coords}
        onPinTap={onPinTap}
      />

      <SearchPulse active={busy} bottom={dockHeight} />

      {turn ? (
        <AnswerBar
          question={turn.question}
          answer={answer?.answer ?? null}
          photoUri={turn.photo?.uri ?? null}
          step={step}
          errorMessage={turn.status === "failed" ? turn.errorMessage : null}
          expanded={expandedAnswer || spots.length === 0}
          collapsible={spots.length > 0}
          top={insets.top + 7}
          onToggle={() => setExpandedAnswer((open) => !open)}
          onClose={onNewChat}
          onRetry={onRetry}
        />
      ) : null}

      <View
        testID="travel-carousel-slot"
        style={[styles.stack, { bottom: dockBase }]}
        pointerEvents="box-none"
      >
        {pending ? <SpotCarouselSkeleton /> : null}
        <SpotCarousel
          spots={spots}
          tagBasis={answer?.tagBasis ?? null}
          focusedIndex={focusedAt}
          scrollToIndex={scrollToAt}
          origin={coords}
          onFocusChange={onFocusChange}
          onDetail={(spot: TravelSpot) => router.push(`/spots/${spot.contentId}`)}
          onSaveToggle={(saved) => setToast(saved ? SAVE_COMPLETE : UNSAVE_COMPLETE)}
          onMetricPress={(tooltip) => {
            if (tooltip) setToast(tooltip);
          }}
        />
      </View>

      <TravelDock
        value={draft}
        photo={photo}
        chips={chips}
        disabled={busy}
        placeholder={placeholder}
        locationAskable={locationAskable}
        bottom={0}
        onChange={setDraft}
        onChipPress={(chip) => void onChipPress(chip)}
        onShoot={() => void onShoot()}
        onClearAttach={() => setPhoto(null)}
        onSubmit={() => submit(draft, photo)}
        onFocus={() => setExpandedChips(false)}
        onAskLocation={() => void askLocation()}
      />

      <Toast
        testID="travel-toast"
        message={toast}
        bottom={dockHeight + TOAST_LIFT}
        onHide={() => setToast(null)}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  stack: { position: "absolute", left: 0, right: 0 },
});
