import { useCallback, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Animated,
  PanResponder,
  Pressable,
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
import type { HomeSpotCard } from "@/features/home/api";
import { colors, spacing } from "@/constants/theme";

const MIN_SAVES = 3;
const BG = "#141216";
const SWIPE_THRESHOLD = 110;
const FLING_VELOCITY = 0.5;
const EXIT_MS = 190;
const RETURN_TENSION = 55;
const MAX_TILT_DEG = 9;

type Decision = "keep" | "skip";

export function TastePicker() {
  const insets = useSafeAreaInsets();
  const { width, height } = useWindowDimensions();
  const { data, isLoading, isError } = useTastePicks();
  const { data: savedList, isLoading: savedLoading } = useSavedList();
  const saveMut = useSaveMutation();

  const [index, setIndex] = useState(0);
  const [savedIds, setSavedIds] = useState<string[]>([]);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);

  const [pan] = useState(() => new Animated.ValueXY({ x: 0, y: 0 }));

  const [deck, setDeck] = useState<HomeSpotCard[] | null>(null);
  if (deck === null && data && !savedLoading) {
    const items = data.items ?? [];
    const unsaved = items.filter((c) => !containsId(savedList, c.contentId));
    setDeck(unsaved.length > 0 ? unsaved : items);
  }
  const cards = useMemo(() => deck ?? [], [deck]);

  const card = cards[index];
  const upcoming = cards[index + 1];
  const done = cards.length > 0 && index >= cards.length;
  const enough = savedIds.length >= MIN_SAVES;

  const close = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["home-recommendations"] });
    router.back();
  }, []);

  const settle = useCallback(
    (decided: HomeSpotCard) => {
      pan.setValue({ x: 0, y: 0 });
      setIndex((i) => (cards[i]?.contentId === decided.contentId ? i + 1 : i));
    },
    [cards, pan],
  );

  const springBack = useCallback(() => {
    Animated.spring(pan, {
      toValue: { x: 0, y: 0 },
      tension: RETURN_TENSION,
      friction: 7,
      useNativeDriver: true,
    }).start();
  }, [pan]);

  const decide = useCallback(
    (decision: Decision) => {
      const target = cards[index];
      if (!target || busy) return;
      setBusy(true);
      setFailed(false);

      const flyTo = decision === "keep" ? width * 1.4 : -width * 1.4;
      const flight = new Promise<void>((resolve) => {
        Animated.timing(pan, {
          toValue: { x: flyTo, y: 0 },
          duration: EXIT_MS,
          useNativeDriver: true,
        }).start(() => resolve());
      });

      void (async () => {
        try {
          if (decision === "keep") {
            await Promise.all([saveMut.mutateAsync(target.contentId), flight]);
            setSavedIds((ids) =>
              ids.includes(target.contentId) ? ids : [...ids, target.contentId],
            );
          } else {
            await flight;
          }
          settle(target);
        } catch {
          setFailed(true);
          springBack();
        } finally {
          setBusy(false);
        }
      })();
    },
    [busy, cards, index, pan, saveMut, settle, springBack, width],
  );

  const responder = useMemo(
    () =>
      PanResponder.create({
        onMoveShouldSetPanResponder: (_e, g) =>
          !busy && Math.abs(g.dx) > 8 && Math.abs(g.dx) > Math.abs(g.dy),
        onPanResponderMove: (_e, g) => {
          if (busy) return;
          pan.setValue({ x: g.dx, y: g.dy * 0.25 });
        },
        onPanResponderRelease: (_e, g) => {
          if (busy) return;
          const flung = Math.abs(g.vx) > FLING_VELOCITY;
          if (g.dx > SWIPE_THRESHOLD || (flung && g.vx > 0)) decide("keep");
          else if (g.dx < -SWIPE_THRESHOLD || (flung && g.vx < 0)) decide("skip");
          else springBack();
        },
        onPanResponderTerminate: () => springBack(),
      }),
    [busy, decide, pan, springBack],
  );

  if (isLoading) {
    return (
      <View style={[styles.root, styles.centered]}>
        <ActivityIndicator color={colors.onImage} />
        <Text style={styles.muted}>취향 카드를 준비하고 있어요</Text>
      </View>
    );
  }

  if (isError || cards.length === 0) {
    return (
      <View style={[styles.root, styles.centered]}>
        <Text style={styles.muted}>지금은 보여줄 카드가 없어요</Text>
        <Pressable testID="taste-close" onPress={close} style={styles.finishButton}>
          <Text style={styles.finishText}>돌아가기</Text>
        </Pressable>
      </View>
    );
  }

  const cardWidth = width - spacing.lg * 2;
  const cardHeight = Math.min(Math.round(cardWidth * 1.25), height - insets.top - 300);

  const rotate = pan.x.interpolate({
    inputRange: [-width, 0, width],
    outputRange: [`-${MAX_TILT_DEG}deg`, "0deg", `${MAX_TILT_DEG}deg`],
  });
  const keepOpacity = pan.x.interpolate({
    inputRange: [0, SWIPE_THRESHOLD],
    outputRange: [0, 1],
    extrapolate: "clamp",
  });
  const skipOpacity = pan.x.interpolate({
    inputRange: [-SWIPE_THRESHOLD, 0],
    outputRange: [1, 0],
    extrapolate: "clamp",
  });
  const nextScale = pan.x.interpolate({
    inputRange: [-SWIPE_THRESHOLD, 0, SWIPE_THRESHOLD],
    outputRange: [1, 0.94, 1],
    extrapolate: "clamp",
  });

  return (
    <View style={[styles.root, { paddingTop: insets.top + 12 }]}>
      <View style={styles.topRow}>
        <Text testID="taste-progress" style={styles.progress}>
          {`${savedIds.length}/${MIN_SAVES} 저장`}
        </Text>
        <Pressable testID="taste-close" onPress={close} hitSlop={10} style={styles.iconButton}>
          <Icon name="close" size={18} color={colors.onImage} />
        </Pressable>
      </View>

      <View style={styles.segments}>
        {cards.map((c, i) => (
          <View key={c.contentId} style={styles.segTrack}>
            <View style={[styles.segFill, { opacity: i < index ? 1 : i === index ? 0.6 : 0.25 }]} />
          </View>
        ))}
      </View>

      {done ? (
        <View style={styles.centered}>
          <Icon name="sparkle" size={34} color={colors.accentText} />
          <Text style={styles.doneTitle}>
            {enough ? "취향을 다 읽었어요" : "조금 더 저장해 볼까요?"}
          </Text>
          <Text style={styles.muted}>
            {enough
              ? "홈에서 추천 장소를 확인해 보세요."
              : `${MIN_SAVES}곳 이상 저장하면 추천이 시작돼요.`}
          </Text>
          <Pressable testID="taste-finish" onPress={close} style={styles.finishButton}>
            <Text style={styles.finishText}>홈으로 돌아가기</Text>
          </Pressable>
        </View>
      ) : (
        <>
          <View style={styles.cardWrap}>
            {upcoming ? (
              <Animated.View
                pointerEvents="none"
                style={[
                  styles.card,
                  styles.stacked,
                  { width: cardWidth, height: cardHeight, transform: [{ scale: nextScale }] },
                ]}
              >
                <RemoteImage uri={upcoming.imageUrl} style={StyleSheet.absoluteFill} />
              </Animated.View>
            ) : null}

            <Animated.View
              testID="taste-card"
              {...responder.panHandlers}
              style={[
                styles.card,
                {
                  width: cardWidth,
                  height: cardHeight,
                  transform: [{ translateX: pan.x }, { translateY: pan.y }, { rotate }],
                },
              ]}
            >
              <RemoteImage uri={card.imageUrl} style={StyleSheet.absoluteFill} />
              <Svg style={StyleSheet.absoluteFill} width="100%" height="100%" pointerEvents="none">
                <Defs>
                  <LinearGradient id="tasteScrim" x1="0" y1="0" x2="0" y2="1">
                    <Stop offset="0.4" stopColor={BG} stopOpacity={0} />
                    <Stop offset="1" stopColor={BG} stopOpacity={0.85} />
                  </LinearGradient>
                </Defs>
                <Rect x="0" y="0" width="100%" height="100%" fill="url(#tasteScrim)" />
              </Svg>

              <Animated.View
                pointerEvents="none"
                style={[styles.stamp, styles.stampKeep, { opacity: keepOpacity }]}
              >
                <Text style={[styles.stampText, styles.stampKeepText]}>저장</Text>
              </Animated.View>
              <Animated.View
                pointerEvents="none"
                style={[styles.stamp, styles.stampSkip, { opacity: skipOpacity }]}
              >
                <Text style={styles.stampText}>패스</Text>
              </Animated.View>

              <View style={styles.cardMeta}>
                <Text style={styles.cardTitle} numberOfLines={2}>
                  {card.title}
                </Text>
                <Text style={styles.cardRegion} numberOfLines={1}>
                  {[card.category, card.regionLabel].filter(Boolean).join(" · ")}
                </Text>
              </View>
            </Animated.View>
          </View>

          <Text style={styles.hint}>좌우로 밀어 보세요 — 오른쪽은 저장, 왼쪽은 패스예요</Text>

          {failed ? (
            <Text testID="taste-error" style={styles.error}>
              저장하지 못했어요. 연결을 확인하고 다시 시도해 주세요.
            </Text>
          ) : null}

          <View style={[styles.actions, { paddingBottom: insets.bottom + spacing.lg }]}>
            <Pressable
              testID="taste-skip"
              disabled={busy}
              onPress={() => decide("skip")}
              style={[styles.skip, busy && styles.dimmed]}
            >
              <Icon name="close" size={24} color={colors.sec} />
            </Pressable>
            <Pressable
              testID="taste-keep"
              disabled={busy}
              onPress={() => decide("keep")}
              style={[styles.keep, busy && styles.dimmed]}
            >
              {busy ? (
                <ActivityIndicator color={colors.onImage} />
              ) : (
                <>
                  <Icon name="bookmark-fill" size={26} color={colors.onImage} />
                  <Text style={styles.keepText}>저장</Text>
                </>
              )}
            </Pressable>
          </View>
        </>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: BG, paddingHorizontal: spacing.lg },
  centered: { flex: 1, alignItems: "center", justifyContent: "center", gap: spacing.md },
  muted: { fontSize: 14, color: colors.sec, textAlign: "center" },
  topRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  progress: { fontSize: 14, fontWeight: "800", color: colors.onImage },
  iconButton: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.glassFill,
    borderWidth: 1,
    borderColor: colors.glassBorder,
  },
  segments: { flexDirection: "row", gap: 4, marginTop: spacing.md },
  segTrack: {
    flex: 1,
    height: 3,
    borderRadius: 2,
    overflow: "hidden",
    backgroundColor: "rgba(255,255,255,0.22)",
  },
  segFill: { flex: 1, backgroundColor: colors.onImage },
  cardWrap: { flex: 1, alignItems: "center", justifyContent: "center" },
  card: { borderRadius: 20, overflow: "hidden", backgroundColor: colors.inset },
  stacked: { position: "absolute", opacity: 0.5 },
  cardMeta: { position: "absolute", left: 20, right: 20, bottom: 20, gap: 4 },
  cardTitle: { fontSize: 22, fontWeight: "800", letterSpacing: -0.6, color: colors.onImage },
  cardRegion: { fontSize: 13.5, fontWeight: "600", color: colors.onDim },
  stamp: {
    position: "absolute",
    top: 22,
    paddingHorizontal: 14,
    paddingVertical: 7,
    borderRadius: 10,
    borderWidth: 3,
  },
  stampKeep: { left: 20, borderColor: colors.accent, transform: [{ rotate: "-12deg" }] },
  stampSkip: { right: 20, borderColor: colors.onDim, transform: [{ rotate: "12deg" }] },
  stampText: { fontSize: 22, fontWeight: "900", letterSpacing: 1, color: colors.onDim },
  stampKeepText: { color: colors.accent },
  hint: { marginTop: spacing.md, fontSize: 12.5, color: colors.sec, textAlign: "center" },
  error: { marginTop: 6, fontSize: 12.5, color: colors.accentText, textAlign: "center" },
  actions: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 14,
    marginTop: spacing.md,
  },
  dimmed: { opacity: 0.5 },
  skip: {
    width: 60,
    height: 60,
    borderRadius: 30,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.fill,
  },
  keep: {
    flex: 1,
    height: 60,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    borderRadius: 30,
    backgroundColor: colors.accent,
  },
  keepText: { fontSize: 16, fontWeight: "800", color: colors.onImage },
  doneTitle: { fontSize: 20, fontWeight: "800", letterSpacing: -0.4, color: colors.ink },
  finishButton: {
    marginTop: spacing.sm,
    paddingHorizontal: 22,
    height: 50,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.fillStrong,
  },
  finishText: { fontSize: 15, fontWeight: "700", color: colors.ink },
});
