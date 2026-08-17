import { useCallback, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
  useWindowDimensions,
} from "react-native";
import Svg, { Defs, LinearGradient, Rect, Stop } from "react-native-svg";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router } from "expo-router";
import { Icon } from "@/components/Icon";
import { RemoteImage } from "@/components/RemoteImage";
import { useTastePicks } from "@/features/home/queries";
import { useSavedList, useSaveMutation } from "@/features/saved/queries";
import { containsId } from "@/features/saved/lib/optimistic";
import { queryClient } from "@/lib/query-client";
import type { HomeSpotCard, TasteCategory } from "@/features/home/api";
import { colors, spacing } from "@/constants/theme";

const CATEGORIES: TasteCategory[] = ["SPOT", "CAFE", "FOOD", "FESTA", "HIDDEN"];
const MIN_PICKS = 3;
const PAGE_SIZE = 12;
const POOL_SIZE = 24;
const GUTTER = 2;

interface Rotation {
  slots: string[];
  queue: string[];
}

function rotate(slots: string[], queue: string[], keep: (id: string) => boolean) {
  const nextQueue = [...queue];
  const nextSlots = slots.map((id) => {
    if (keep(id) || nextQueue.length === 0) return id;
    const incoming = nextQueue.shift() as string;
    nextQueue.push(id);
    return incoming;
  });
  return { slots: nextSlots, queue: nextQueue };
}

export function TastePicker() {
  const insets = useSafeAreaInsets();
  const { width } = useWindowDimensions();
  const [category, setCategory] = useState<TasteCategory>("SPOT");
  const { data, isLoading, isError } = useTastePicks(POOL_SIZE, category);
  const { data: savedList, isLoading: savedLoading } = useSavedList();
  const saveMut = useSaveMutation();
  const scrollRef = useRef<ScrollView>(null);

  const [picked, setPicked] = useState<string[]>([]);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [pools, setPools] = useState<Partial<Record<TasteCategory, HomeSpotCard[]>>>({});
  const [rotations, setRotations] = useState<Partial<Record<TasteCategory, Rotation>>>({});

  if (pools[category] === undefined && data && !savedLoading) {
    const items = data.items ?? [];
    const unsaved = items.filter((c) => !containsId(savedList, c.contentId));
    const next = unsaved.length > 0 ? unsaved : items;
    setPools((prev) => ({ ...prev, [category]: next }));
    setRotations((prev) => ({
      ...prev,
      [category]: {
        slots: next.slice(0, PAGE_SIZE).map((c) => c.contentId),
        queue: next.slice(PAGE_SIZE).map((c) => c.contentId),
      },
    }));
  }

  const byId = useMemo(() => {
    const map = new Map<string, HomeSpotCard>();
    Object.values(pools).forEach((cards) =>
      (cards ?? []).forEach((card) => map.set(card.contentId, card)),
    );
    return map;
  }, [pools]);

  const rotation = rotations[category];
  const shown = (rotation?.slots ?? [])
    .map((id) => byId.get(id))
    .filter((card): card is HomeSpotCard => card !== undefined);
  const canRotate = (rotation?.queue.length ?? 0) > 0;
  const enough = picked.length >= MIN_PICKS;
  const poolReady = pools[category] !== undefined;

  const close = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["home-recommendations"] });
    router.back();
  }, []);

  const toggle = useCallback((contentId: string) => {
    setFailed(false);
    setPicked((ids) =>
      ids.includes(contentId) ? ids.filter((id) => id !== contentId) : [...ids, contentId],
    );
  }, []);

  const refresh = useCallback(() => {
    setRotations((prev) => {
      const current = prev[category];
      if (!current) return prev;
      return {
        ...prev,
        [category]: rotate(current.slots, current.queue, (id) => picked.includes(id)),
      };
    });
  }, [category, picked]);

  const switchCategory = useCallback((next: TasteCategory) => {
    setCategory(next);
    scrollRef.current?.scrollTo({ y: 0, animated: false });
  }, []);

  const submit = useCallback(() => {
    if (!enough || busy) return;
    setBusy(true);
    setFailed(false);
    void (async () => {
      try {
        await Promise.all(picked.map((contentId) => saveMut.mutateAsync(contentId)));
        close();
      } catch {
        setFailed(true);
      } finally {
        setBusy(false);
      }
    })();
  }, [busy, close, enough, picked, saveMut]);

  if (isLoading && !poolReady && picked.length === 0) {
    return (
      <View style={[styles.root, styles.centered]}>
        <ActivityIndicator color={colors.ink} />
        <Text style={styles.muted}>취향 카드를 준비하고 있어요</Text>
      </View>
    );
  }

  if ((isError || shown.length === 0) && picked.length === 0 && !isLoading) {
    return (
      <View style={[styles.root, styles.centered]}>
        <Text style={styles.muted}>지금은 보여줄 장소가 없어요</Text>
        <Pressable testID="taste-close" onPress={close} style={styles.ghostButton}>
          <Text style={styles.ghostText}>돌아가기</Text>
        </Pressable>
      </View>
    );
  }

  const tileSize = Math.floor((width - GUTTER * 2) / 3);

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <View style={styles.nav}>
        <Pressable
          testID="taste-close"
          accessibilityRole="button"
          accessibilityLabel="닫기"
          hitSlop={10}
          onPress={close}
          style={styles.navButton}
        >
          <Icon name="chevron-left" size={23} color={colors.ink} />
        </Pressable>
        <Text style={styles.navTitle}>취향 고르기</Text>
        {canRotate ? (
          <Pressable
            testID="taste-refresh"
            accessibilityRole="button"
            accessibilityLabel="다른 장소 보기"
            hitSlop={10}
            onPress={refresh}
            style={styles.navButton}
          >
            <Icon name="refresh" size={21} color={colors.ink} />
          </Pressable>
        ) : (
          <View style={styles.navButton} />
        )}
      </View>

      <View style={styles.lead}>
        <Text style={styles.leadTitle}>마음에 드는 곳을 골라주세요</Text>
      </View>

      <View style={styles.chips}>
        {CATEGORIES.map((c) => {
          const active = c === category;
          return (
            <Pressable
              key={c}
              testID={`taste-category-${c}`}
              accessibilityRole="tab"
              accessibilityState={{ selected: active }}
              onPress={() => switchCategory(c)}
              style={[styles.chip, active && styles.chipActive]}
            >
              <Text style={[styles.chipText, active && styles.chipTextActive]}>{c}</Text>
            </Pressable>
          );
        })}
      </View>

      <ScrollView
        ref={scrollRef}
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.scroll}
      >
        {isLoading && !poolReady ? (
          <View style={styles.gridLoading}>
            <ActivityIndicator color={colors.ink} />
          </View>
        ) : (
          <View style={styles.grid}>
            {shown.map((card) => (
              <TasteTile
                key={card.contentId}
                card={card}
                size={tileSize}
                selected={picked.includes(card.contentId)}
                onPress={() => toggle(card.contentId)}
              />
            ))}
          </View>
        )}
      </ScrollView>

      <View style={[styles.dock, { paddingBottom: insets.bottom + spacing.md }]}>
        {failed ? (
          <Text testID="taste-error" style={styles.error}>
            저장하지 못했어요. 연결을 확인하고 다시 시도해 주세요.
          </Text>
        ) : null}
        <Pressable
          testID="taste-done"
          accessibilityRole="button"
          accessibilityState={{ disabled: !enough || busy }}
          onPress={submit}
          style={[styles.done, (!enough || busy) && styles.doneDisabled]}
        >
          {busy ? (
            <ActivityIndicator color={colors.onImage} />
          ) : (
            <Text style={styles.doneText}>완료</Text>
          )}
        </Pressable>
      </View>
    </View>
  );
}

function TasteTile({
  card,
  size,
  selected,
  onPress,
}: {
  card: HomeSpotCard;
  size: number;
  selected: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      testID={`taste-card-${card.contentId}`}
      accessibilityRole="checkbox"
      accessibilityState={{ checked: selected, selected }}
      onPress={onPress}
      style={{ width: size, height: size }}
    >
      <RemoteImage uri={card.imageUrl} style={StyleSheet.absoluteFill} midSize />
      <Svg style={StyleSheet.absoluteFill} width="100%" height="100%" pointerEvents="none">
        <Defs>
          <LinearGradient id="tasteTileScrim" x1="0" y1="0" x2="0" y2="1">
            <Stop offset="0.46" stopColor="#0B0D11" stopOpacity={0} />
            <Stop offset="1" stopColor="#0B0D11" stopOpacity={0.62} />
          </LinearGradient>
        </Defs>
        <Rect x="0" y="0" width="100%" height="100%" fill="url(#tasteTileScrim)" />
      </Svg>
      <Text style={styles.tileName} numberOfLines={1}>
        {card.title}
      </Text>
      <View style={[styles.tileCheck, selected && styles.tileCheckOn]}>
        {selected ? <Icon name="check" size={13} color={colors.onImage} strokeWidth={2.8} /> : null}
      </View>
      {selected ? <View style={styles.tileRing} pointerEvents="none" /> : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  centered: { alignItems: "center", justifyContent: "center", gap: spacing.md },
  muted: { fontSize: 14, color: colors.sec },
  ghostButton: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    borderRadius: 999,
    backgroundColor: colors.fill,
  },
  ghostText: { fontSize: 14, fontWeight: "700", color: colors.ink },
  nav: {
    height: 50,
    flexDirection: "row",
    alignItems: "center",
  },
  navButton: { width: 46, alignItems: "center", justifyContent: "center" },
  navTitle: {
    flex: 1,
    textAlign: "center",
    fontSize: 17,
    fontWeight: "700",
    color: colors.ink,
  },
  lead: { paddingHorizontal: spacing.lg, paddingTop: spacing.xs },
  leadTitle: {
    fontSize: 19,
    fontWeight: "800",
    letterSpacing: -0.6,
    lineHeight: 26,
    color: colors.ink,
  },
  chips: {
    flexDirection: "row",
    gap: 7,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: 12,
  },
  chip: {
    height: 34,
    paddingHorizontal: 15,
    borderRadius: 17,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.fill,
    borderWidth: 1,
    borderColor: colors.line,
  },
  chipActive: { backgroundColor: colors.accent, borderColor: colors.accent },
  chipText: { fontSize: 12.5, fontWeight: "700", letterSpacing: 0.3, color: colors.sec },
  chipTextActive: { color: colors.onImage, fontWeight: "800" },
  scroll: { paddingBottom: spacing.lg },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: GUTTER },
  gridLoading: { paddingTop: 80, alignItems: "center" },
  tileName: {
    position: "absolute",
    left: 8,
    right: 8,
    bottom: 7,
    fontSize: 11.5,
    fontWeight: "700",
    letterSpacing: -0.2,
    color: colors.onImage,
  },
  tileCheck: {
    position: "absolute",
    top: 7,
    right: 7,
    width: 22,
    height: 22,
    borderRadius: 11,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.control,
    borderWidth: 1.5,
    borderColor: "rgba(255,255,255,0.6)",
  },
  tileCheckOn: { backgroundColor: colors.accent, borderWidth: 0 },
  tileRing: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    borderWidth: 3,
    borderColor: colors.accent,
  },
  dock: {
    paddingHorizontal: spacing.lg,
    paddingTop: 12,
    gap: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.line,
    backgroundColor: colors.bg,
  },
  error: { fontSize: 13, color: colors.danger, textAlign: "center" },
  done: {
    height: 48,
    borderRadius: 8,
    backgroundColor: colors.accent,
    alignItems: "center",
    justifyContent: "center",
  },
  doneDisabled: { opacity: 0.4 },
  doneText: { fontSize: 15, fontWeight: "700", color: colors.onImage },
});
