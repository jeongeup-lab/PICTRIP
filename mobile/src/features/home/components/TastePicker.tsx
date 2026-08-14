import { useCallback, useMemo, useState } from "react";
import { Animated, PanResponder, useWindowDimensions } from "react-native";
import { router } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import type { HomeSpotCard } from "@/features/home/api";
import { useTastePicks } from "@/features/home/queries";
import { containsId } from "@/features/saved/lib/optimistic";
import { useSavedList, useSaveMutation, useUnsaveMutation } from "@/features/saved/queries";
import { TastePickerView } from "@/features/home/components/TastePickerView";
import { queryClient } from "@/lib/query-client";

const MIN_SAVES = 3;
const SWIPE_THRESHOLD = 110;
const FLING_VELOCITY = 0.5;
const EXIT_MS = 190;

type Decision = "keep" | "skip";
type History = { readonly index: number; readonly savedInSession: boolean };

function createDecisionLock() {
  let locked = false;
  return {
    acquire() {
      if (locked) return false;
      locked = true;
      return true;
    },
    release() {
      locked = false;
    },
  };
}

export function TastePicker() {
  const insets = useSafeAreaInsets();
  const { width, height } = useWindowDimensions();
  const { data, isLoading, isError } = useTastePicks();
  const { data: savedList, isLoading: savedLoading } = useSavedList();
  const saveMut = useSaveMutation();
  const unsaveMut = useUnsaveMutation();
  const [index, setIndex] = useState(0);
  const [savedIds, setSavedIds] = useState<readonly string[]>([]);
  const [history, setHistory] = useState<History | null>(null);
  const [error, setError] = useState<"save" | "undo" | null>(null);
  const [busy, setBusy] = useState(false);
  const decisionLock = useMemo(() => createDecisionLock(), []);
  const [pan] = useState(() => new Animated.ValueXY({ x: 0, y: 0 }));
  const [deck, setDeck] = useState<HomeSpotCard[] | null>(null);
  const [baseSavedCount, setBaseSavedCount] = useState(0);

  if (deck === null && data && !savedLoading) {
    const items = data.items ?? [];
    const unsaved = items.filter((item) => !containsId(savedList, item.contentId));
    setDeck(unsaved.length > 0 ? unsaved : items);
    setBaseSavedCount(savedList?.length ?? 0);
  }

  const cards = useMemo(() => deck ?? [], [deck]);
  const card = cards[index];
  const upcoming = cards[index + 1];
  const done = cards.length > 0 && index >= cards.length;
  const close = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["home-recommendations"] });
    router.back();
  }, []);
  const begin = useCallback(() => {
    if (!decisionLock.acquire()) return false;
    setBusy(true);
    setError(null);
    return true;
  }, [decisionLock]);
  const finish = useCallback(() => {
    decisionLock.release();
    setBusy(false);
  }, [decisionLock]);
  const springBack = useCallback(() => {
    Animated.spring(pan, {
      toValue: { x: 0, y: 0 },
      tension: 55,
      friction: 7,
      useNativeDriver: true,
    }).start();
  }, [pan]);
  const settle = useCallback(
    (decidedIndex: number, savedInSession: boolean) => {
      pan.setValue({ x: 0, y: 0 });
      setHistory({ index: decidedIndex, savedInSession });
      setIndex(decidedIndex + 1);
    },
    [pan],
  );
  const fly = useCallback(
    (decision: Decision) =>
      new Promise<void>((resolve) => {
        Animated.timing(pan, {
          toValue: { x: decision === "keep" ? width * 1.4 : -width * 1.4, y: 0 },
          duration: EXIT_MS,
          useNativeDriver: true,
        }).start(() => resolve());
      }),
    [pan, width],
  );
  const decide = useCallback(
    (decision: Decision) => {
      const target = cards[index];
      if (!target || !begin()) return;
      const wasSaved = containsId(savedList, target.contentId);
      void (async () => {
        try {
          const flight = fly(decision);
          if (decision === "keep" && !wasSaved) {
            await Promise.all([saveMut.mutateAsync(target.contentId), flight]);
            setSavedIds((ids) => [...ids, target.contentId]);
            settle(index, true);
            return;
          }
          await flight;
          settle(index, false);
        } catch {
          setError("save");
          springBack();
        } finally {
          finish();
        }
      })();
    },
    [begin, cards, finish, fly, index, saveMut, savedList, settle, springBack],
  );
  const undo = useCallback(() => {
    if (!history || !begin()) return;
    const target = cards[history.index];
    void (async () => {
      try {
        if (history.savedInSession && target) {
          await unsaveMut.mutateAsync(target.contentId);
          setSavedIds((ids) => ids.filter((id) => id !== target.contentId));
        }
        pan.setValue({ x: 0, y: 0 });
        setIndex(history.index);
        setHistory(null);
      } catch {
        setError("undo");
      } finally {
        finish();
      }
    })();
  }, [begin, cards, finish, history, pan, unsaveMut]);
  const responder = useMemo(
    () =>
      PanResponder.create({
        onMoveShouldSetPanResponder: (_event, gesture) =>
          !busy && Math.abs(gesture.dx) > 8 && Math.abs(gesture.dx) > Math.abs(gesture.dy),
        onPanResponderMove: (_event, gesture) => {
          if (!busy) pan.setValue({ x: gesture.dx, y: gesture.dy * 0.25 });
        },
        onPanResponderRelease: (_event, gesture) => {
          if (busy) return;
          const flung = Math.abs(gesture.vx) > FLING_VELOCITY;
          if (gesture.dx > SWIPE_THRESHOLD || (flung && gesture.vx > 0)) decide("keep");
          else if (gesture.dx < -SWIPE_THRESHOLD || (flung && gesture.vx < 0)) decide("skip");
          else springBack();
        },
        onPanResponderTerminate: springBack,
      }),
    [busy, decide, pan, springBack],
  );

  return (
    <TastePickerView
      cards={cards}
      activeCard={card}
      upcomingCard={upcoming}
      reviewedCount={index}
      enoughSaves={baseSavedCount + savedIds.length >= MIN_SAVES}
      isLoading={isLoading}
      unavailable={isError || cards.length === 0}
      done={done}
      busy={busy}
      error={error}
      hasHistory={history !== null}
      pan={pan}
      responder={responder}
      width={width}
      height={height}
      topInset={insets.top}
      bottomInset={insets.bottom}
      onClose={close}
      onUndo={undo}
      onSave={() => decide("keep")}
      onSkip={() => decide("skip")}
    />
  );
}
