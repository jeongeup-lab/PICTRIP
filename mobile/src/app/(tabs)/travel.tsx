import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ScrollView, Pressable, View, Text, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router } from "expo-router";
import { Icon } from "@/components/Icon";
import { GlassSheet, SCREEN_H } from "@/components/GlassSheet";
import { Toast } from "@/components/Toast";
import { KakaoWebMap } from "@/features/map/components/KakaoWebMap";
import { AskComposer } from "@/features/travel/components/AskComposer";
import { AnchorPreview } from "@/features/travel/components/AnchorPreview";
import { ConversationTurn } from "@/features/travel/components/ConversationTurn";
import { Mascot } from "@/features/travel/components/Mascot";
import { SearchPulse } from "@/features/travel/components/SearchPulse";
import { StartActions } from "@/features/travel/components/StartActions";
import { useNearbyCoords } from "@/features/travel/hooks/use-nearby-coords";
import { useCardTap } from "@/features/travel/hooks/use-card-tap";
import { useAuthGate } from "@/features/auth/hooks/use-auth-gate";
import { useAskAgentMutation } from "@/features/travel/queries";
import { useConversation, type Turn } from "@/features/travel/stores/conversation-store";
import { useTravelAnchor } from "@/features/travel/stores/anchor-store";
import {
  agentErrorMessage,
  PHOTO_PICK_FAILED,
  PHOTO_SHOOT_FAILED,
} from "@/features/travel/lib/agent-errors";
import { composeQuestion, anchorQuestion, MY_LOCATION } from "@/features/travel/lib/question";
import { composerChips, FESTIVAL_CHIP, NEARBY_CHIP, type Chip } from "@/features/travel/lib/chips";
import { contextFrom } from "@/features/travel/lib/conversation-context";
import {
  TAB_BAR_CONTENT_PX,
  travelSheetSnapY,
  type SheetSnap,
} from "@/features/travel/lib/sheet-snap";
import { coordsOf, spotDistanceKm } from "@/features/travel/lib/distance";
import { pickTravelPhoto, shootTravelPhoto } from "@/features/travel/usecases/pick-travel-photo";
import {
  bounds,
  center,
  pinsFrom,
  placed,
  spatialSummary,
  summaryLine,
} from "@/features/travel/lib/spot-geo";
import { mapListPaddingBottom } from "@/features/map/lib/list-padding";
import type { AskInput, PhotoUpload, TravelSpot } from "@/features/travel/api";
import { colors, radii, spacing } from "@/constants/theme";

const SAVE_COMPLETE = "여행지를 저장했어요";
const UNSAVE_COMPLETE = "여행지 저장을 해제했어요";
const TOAST_LIFT = 12;
const FIT_TOP_PAD = 96;
const FIT_SIDE_PAD = 40;
const FIT_BOTTOM_MARGIN = 24;

export const TAGLINE = "사진 한 장으로 떠나는 여행";

export const GREETING = "오늘, 어디로 갈까요";

export default function TravelScreen() {
  const insets = useSafeAreaInsets();
  const scrollRef = useRef<ScrollView>(null);
  const [draft, setDraft] = useState("");
  const [photo, setPhoto] = useState<PhotoUpload | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [snap, setSnap] = useState<SheetSnap>("peek");
  const [everAnchored, setEverAnchored] = useState(false);

  const turns = useConversation((s) => s.turns);
  const busy = useConversation((s) => s.busy);
  const startTurn = useConversation((s) => s.start);
  const retryTurn = useConversation((s) => s.retry);
  const resolveTurn = useConversation((s) => s.resolve);
  const failTurn = useConversation((s) => s.fail);
  const clearTurns = useConversation((s) => s.clear);
  const nextTurnId = useConversation((s) => s.nextTurnId);

  const anchorSpot = useTravelAnchor((s) => s.spot);
  const toggleAnchor = useTravelAnchor((s) => s.toggle);
  const pickAnchor = useTravelAnchor((s) => s.pick);
  const clearAnchor = useTravelAnchor((s) => s.clear);

  const { coords, askable: locationAskable, ask: askLocation } = useNearbyCoords();
  const ask = useAskAgentMutation();
  const requireAuth = useAuthGate();

  const empty = turns.length === 0;
  const snapY = useMemo(
    () => travelSheetSnapY(SCREEN_H, TAB_BAR_CONTENT_PX + insets.bottom),
    [insets],
  );

  const lastAnswered = [...turns].reverse().find((t) => t.status === "done" && t.answer);
  const tapHintTurnId = turns.find((t) => (t.answer?.spots.length ?? 0) > 0)?.id ?? null;

  const mapSpots = useMemo(() => {
    const shown = placed(lastAnswered?.answer?.spots ?? []);
    if (!anchorSpot || shown.some((s) => s.spot.contentId === anchorSpot.contentId)) return shown;
    const at = coordsOf(anchorSpot);
    return at ? [...shown, { spot: anchorSpot, lat: at.lat, lng: at.lng }] : shown;
  }, [lastAnswered, anchorSpot]);

  const pins = useMemo(() => pinsFrom(mapSpots), [mapSpots]);
  const fit = useMemo(() => {
    const box = bounds(mapSpots);
    if (!box) return null;
    return {
      ...box,
      pad: {
        top: insets.top + FIT_TOP_PAD,
        right: FIT_SIDE_PAD,
        bottom: SCREEN_H - snapY[snap] + FIT_BOTTOM_MARGIN,
        left: FIT_SIDE_PAD,
      },
    };
  }, [mapSpots, snap, snapY, insets]);
  const focus = useMemo(() => {
    if (anchorSpot) return coordsOf(anchorSpot) ?? center(mapSpots) ?? coords;
    return center(mapSpots) ?? coords;
  }, [anchorSpot, mapSpots, coords]);

  const origin = anchorSpot ? coordsOf(anchorSpot) : coords;
  const summary = useMemo(() => summaryLine(spatialSummary(mapSpots)), [mapSpots]);

  const scrollFrame = useRef<number | null>(null);

  useEffect(
    () => () => {
      if (scrollFrame.current !== null) cancelAnimationFrame(scrollFrame.current);
    },
    [],
  );

  const scrollToEnd = useCallback(() => {
    scrollFrame.current = requestAnimationFrame(() =>
      scrollRef.current?.scrollToEnd({ animated: true }),
    );
  }, []);

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
      const id = nextTurnId();
      const context = contextFrom(lastAnswered?.answer, anchorSpot?.contentId ?? null);
      startTurn({ id, question, request, photo: attached, context });
      setDraft("");
      setPhoto(null);
      setSnap("half");
      scrollToEnd();
      run(id, { question: request, photo: attached, context });
    },
    [busy, startTurn, scrollToEnd, run, lastAnswered, anchorSpot, nextTurnId],
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
        const id = nextTurnId();
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
        setSnap("half");
        scrollToEnd();
        run(id, { anchor });
        return;
      }
      if (chip.kind === "intent") {
        const id = nextTurnId();
        startTurn({ id, question: chip.label, request: "", photo: null, intent: chip.intent });
        setSnap("half");
        scrollToEnd();
        run(id, { intent: chip.intent });
        return;
      }
      const intent = source?.answer?.intent ?? null;
      if (!intent) return;
      const id = nextTurnId();
      const attached = source?.photo ?? null;
      startTurn({
        id,
        question: chip.label,
        request: "",
        photo: attached,
        intent,
        patch: chip.patch,
      });
      setSnap("half");
      scrollToEnd();
      run(id, { photo: attached, intent, patch: chip.patch });
    },
    [busy, submit, anchorSpot, coords, startTurn, scrollToEnd, run, nextTurnId],
  );

  const submitDockChip = useCallback(
    (chip: Chip) => refineFrom(lastAnswered, chip),
    [refineFrom, lastAnswered],
  );

  const onNearby = useCallback(() => submit(NEARBY_CHIP.question, null), [submit]);

  const onFestival = useCallback(() => refineFrom(undefined, FESTIVAL_CHIP), [refineFrom]);

  const openSaved = useCallback(async () => {
    if (await requireAuth("saved-list")) router.push("/saved");
  }, [requireAuth]);

  const onNewChat = useCallback(() => {
    clearTurns();
    setDraft("");
    setPhoto(null);
    clearAnchor();
    setSnap("peek");
  }, [clearTurns, clearAnchor]);

  const onSpotDetail = useCallback((spot: TravelSpot) => {
    router.push(`/spots/${spot.contentId}`);
  }, []);

  const onSpotAnchor = useCallback(
    (spot: TravelSpot) => {
      setEverAnchored(true);
      toggleAnchor(spot);
    },
    [toggleAnchor],
  );

  const onSpotTap = useCardTap(onSpotAnchor, onSpotDetail);

  const onPinTap = useCallback(
    (contentId: string) => {
      const hit = mapSpots.find((s) => s.spot.contentId === contentId);
      if (!hit) return;
      setEverAnchored(true);
      pickAnchor(hit.spot);
      setSnap("peek");
    },
    [mapSpots, pickAnchor],
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
        context: turn.context,
      });
    },
    [busy, retryTurn, run],
  );

  const onChangeDraft = useCallback((text: string) => setDraft(text), []);

  const attachFrom = useCallback(
    async (source: () => Promise<PhotoUpload | null>, failure: string) => {
      try {
        const picked = await source();
        if (picked) {
          setPhoto(picked);
          clearAnchor();
        }
      } catch {
        setToast(failure);
      }
    },
    [clearAnchor],
  );

  const onSaveToggle = useCallback((saved: boolean) => {
    setToast(saved ? SAVE_COMPLETE : UNSAVE_COMPLETE);
  }, []);

  const onAttach = useCallback(() => attachFrom(pickTravelPhoto, PHOTO_PICK_FAILED), [attachFrom]);

  const onShoot = useCallback(() => attachFrom(shootTravelPhoto, PHOTO_SHOOT_FAILED), [attachFrom]);

  const chips = composerChips(lastAnswered?.answer, anchorSpot, coords !== null);
  const listPaddingBottom = mapListPaddingBottom(
    snapY[snap],
    TAB_BAR_CONTENT_PX + insets.bottom,
    spacing.xxl,
  );

  return (
    <View style={styles.root}>
      <KakaoWebMap
        center={focus}
        fit={fit}
        pins={pins}
        anchorId={anchorSpot?.contentId ?? null}
        userLocation={coords}
        onPinTap={onPinTap}
      />

      <SearchPulse active={busy} bottom={SCREEN_H - snapY[snap]} />

      {lastAnswered && pins.length > 0 ? (
        <View
          testID="travel-map-summary"
          style={[styles.summary, { top: insets.top + spacing.sm }]}
          pointerEvents="none"
        >
          <Text style={styles.summaryTitle} numberOfLines={1}>
            {lastAnswered.question}
          </Text>
          <Text style={styles.summaryLine} numberOfLines={1}>
            {summary ? `${pins.length}곳 · ${summary}` : `${pins.length}곳`}
          </Text>
        </View>
      ) : null}

      <View style={[styles.controls, { top: insets.top + spacing.sm }]} pointerEvents="box-none">
        {empty ? null : (
          <Pressable
            testID="travel-new-chat"
            accessibilityRole="button"
            accessibilityLabel="새 대화"
            style={({ pressed }) => [styles.control, pressed && styles.pressed]}
            hitSlop={6}
            onPress={onNewChat}
          >
            <Icon name="close" size={19} color={colors.ink} strokeWidth={2} />
          </Pressable>
        )}
      </View>

      <GlassSheet
        testID="travel-sheet"
        snap={snap}
        snapY={snapY}
        onSnapChange={setSnap}
        headerExtra={
          <AskComposer
            value={draft}
            photo={photo}
            chips={chips}
            disabled={busy}
            anchorTitle={anchorSpot?.title ?? null}
            onClearAnchor={clearAnchor}
            onChange={onChangeDraft}
            onSuggest={submitDockChip}
            onAttach={() => void onAttach()}
            onShoot={() => void onShoot()}
            onClearAttach={() => setPhoto(null)}
            onSubmit={() => submit(draft, photo)}
            onFocus={() => setSnap("half")}
          />
        }
      >
        <ScrollView
          ref={scrollRef}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={{ paddingBottom: listPaddingBottom }}
        >
          {anchorSpot ? (
            <AnchorPreview
              spot={anchorSpot}
              distanceKm={spotDistanceKm(anchorSpot, coords)}
              onDetail={() => onSpotDetail(anchorSpot)}
              onRelease={clearAnchor}
              onSaveToggle={onSaveToggle}
            />
          ) : null}

          {!empty ? (
            turns.map((turn) => (
              <ConversationTurn
                key={turn.id}
                turn={turn}
                anchorId={anchorSpot?.contentId ?? null}
                anchored={anchorSpot !== null}
                origin={origin}
                showTapHint={!everAnchored && turn.id === tapHintTurnId}
                onSpotTap={onSpotTap}
                onSpotDetail={onSpotDetail}
                onRetry={onRetry}
                onGrow={scrollToEnd}
                onSaveToggle={onSaveToggle}
              />
            ))
          ) : anchorSpot ? null : (
            <View testID="travel-greeting">
              <View style={styles.greeting}>
                <Mascot size={44} floating />
                <View style={styles.greetingCopy}>
                  <Text style={styles.greetingText}>{GREETING}</Text>
                  <Text style={styles.tagline}>{TAGLINE}</Text>
                </View>
              </View>
              <StartActions
                onPhoto={() => void onAttach()}
                onNearby={onNearby}
                onFestival={onFestival}
                onSaved={() => void openSaved()}
                nearbyEnabled={coords !== null}
                onAskLocation={() => void askLocation()}
                locationAskable={locationAskable}
              />
            </View>
          )}
        </ScrollView>
      </GlassSheet>

      <Toast
        testID="travel-toast"
        message={toast}
        bottom={SCREEN_H - snapY[snap] + TOAST_LIFT}
        onHide={() => setToast(null)}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  controls: {
    position: "absolute",
    right: spacing.md,
    gap: 9,
  },
  summary: {
    position: "absolute",
    left: spacing.md,
    right: 70,
    paddingVertical: 9,
    paddingHorizontal: spacing.md,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.glassFill,
  },
  summaryTitle: { fontSize: 13.5, fontWeight: "700", letterSpacing: -0.3, color: colors.ink },
  summaryLine: { marginTop: 3, fontSize: 11.5, color: colors.sec },
  control: {
    width: 42,
    height: 42,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.glassFill,
    alignItems: "center",
    justifyContent: "center",
  },
  pressed: { opacity: 0.7 },
  greeting: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingHorizontal: spacing.lg,
    paddingTop: 16,
  },
  greetingCopy: { flex: 1, minWidth: 0 },
  greetingText: { fontSize: 21, fontWeight: "800", letterSpacing: -0.8, color: colors.ink },
  tagline: { marginTop: 5, fontSize: 12.5, letterSpacing: -0.2, color: colors.ter },
});
