import { useCallback, useMemo, useState } from "react";
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
import type { HomeSpotCard } from "@/features/home/api";
import { colors, spacing } from "@/constants/theme";

const MIN_PICKS = 3;
const PAGE_SIZE = 12;
const POOL_SIZE = 24;
const GUTTER = 10;
const PADDING = spacing.lg;
const IMAGE_RATIO = 1.08;
const FOOTER_HEIGHT = 62;

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
  const { data, isLoading, isError } = useTastePicks(POOL_SIZE);
  const { data: savedList, isLoading: savedLoading } = useSavedList();
  const saveMut = useSaveMutation();

  const [picked, setPicked] = useState<string[]>([]);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [rotation, setRotation] = useState<{ slots: string[]; queue: string[] } | null>(null);

  const [pool, setPool] = useState<HomeSpotCard[] | null>(null);
  if (pool === null && data && !savedLoading) {
    const items = data.items ?? [];
    const unsaved = items.filter((c) => !containsId(savedList, c.contentId));
    const next = unsaved.length > 0 ? unsaved : items;
    setPool(next);
    setRotation({
      slots: next.slice(0, PAGE_SIZE).map((c) => c.contentId),
      queue: next.slice(PAGE_SIZE).map((c) => c.contentId),
    });
  }

  const byId = useMemo(() => {
    const map = new Map<string, HomeSpotCard>();
    (pool ?? []).forEach((card) => map.set(card.contentId, card));
    return map;
  }, [pool]);

  const shown = (rotation?.slots ?? [])
    .map((id) => byId.get(id))
    .filter((card): card is HomeSpotCard => card !== undefined);
  const canRotate = (rotation?.queue.length ?? 0) > 0;
  const enough = picked.length >= MIN_PICKS;

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
    setRotation((current) =>
      current === null
        ? current
        : rotate(current.slots, current.queue, (id) => picked.includes(id)),
    );
  }, [picked]);

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

  if (isLoading) {
    return (
      <View style={[styles.root, styles.centered]}>
        <ActivityIndicator color={colors.ink} />
        <Text style={styles.muted}>취향 카드를 준비하고 있어요</Text>
      </View>
    );
  }

  if (isError || shown.length === 0) {
    return (
      <View style={[styles.root, styles.centered]}>
        <Text style={styles.muted}>지금은 보여줄 장소가 없어요</Text>
        <Pressable testID="taste-close" onPress={close} style={styles.ghostButton}>
          <Text style={styles.ghostText}>돌아가기</Text>
        </Pressable>
      </View>
    );
  }

  const cardWidth = Math.floor((width - PADDING * 2 - GUTTER) / 2);

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

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scroll}>
        <View style={styles.lead}>
          <Text
            style={styles.leadTitle}
          >{`마음이 가는 곳을\n${MIN_PICKS}곳 이상 골라주세요.`}</Text>
          <Text style={styles.leadBody}>고른 곳과 닮은 장소를 홈에서 추천해 드려요.</Text>
        </View>

        <View style={styles.grid}>
          {shown.map((card) => (
            <TasteCard
              key={card.contentId}
              card={card}
              width={cardWidth}
              selected={picked.includes(card.contentId)}
              onPress={() => toggle(card.contentId)}
            />
          ))}
        </View>
      </ScrollView>

      <View style={[styles.dock, { paddingBottom: insets.bottom + spacing.md }]}>
        {failed ? (
          <Text testID="taste-error" style={styles.error}>
            저장하지 못했어요. 연결을 확인하고 다시 시도해 주세요.
          </Text>
        ) : null}
        <Text testID="taste-meter" style={styles.meter}>
          {enough
            ? `${picked.length}곳 골랐어요`
            : picked.length === 0
              ? `${MIN_PICKS}곳 이상 고르면 추천이 시작돼요`
              : `${MIN_PICKS - picked.length}곳만 더 고르면 돼요`}
        </Text>
        <Pressable
          testID="taste-done"
          accessibilityRole="button"
          accessibilityState={{ disabled: !enough || busy }}
          disabled={!enough || busy}
          onPress={submit}
          style={[styles.submit, (!enough || busy) && styles.submitOff]}
        >
          {busy ? (
            <ActivityIndicator color={colors.onImage} />
          ) : (
            <Text style={styles.submitText}>완료</Text>
          )}
        </Pressable>
      </View>
    </View>
  );
}

interface CardProps {
  card: HomeSpotCard;
  width: number;
  selected: boolean;
  onPress: () => void;
}

function TasteCard({ card, width, selected, onPress }: CardProps) {
  const imageHeight = Math.round(width * IMAGE_RATIO);
  return (
    <Pressable
      testID={`taste-card-${card.contentId}`}
      accessibilityRole="button"
      accessibilityState={{ selected }}
      accessibilityLabel={card.title}
      onPress={onPress}
      style={[styles.card, { width }, selected && styles.cardOn]}
    >
      <View style={{ height: imageHeight }}>
        <RemoteImage uri={card.imageUrl} style={StyleSheet.absoluteFill} midSize />
        <Svg style={StyleSheet.absoluteFill} width="100%" height="100%" pointerEvents="none">
          <Defs>
            <LinearGradient id="tasteCardScrim" x1="0" y1="0" x2="0" y2="1">
              <Stop offset="0" stopColor="#0B0D11" stopOpacity={0.35} />
              <Stop offset="0.6" stopColor="#0B0D11" stopOpacity={0.04} />
            </LinearGradient>
          </Defs>
          <Rect x="0" y="0" width="100%" height="100%" fill="url(#tasteCardScrim)" />
        </Svg>
        <View style={[styles.mark, selected && styles.markOn]}>
          {selected ? (
            <Icon name="check" size={14} color={colors.onImage} strokeWidth={2.6} />
          ) : null}
        </View>
      </View>
      <View style={styles.cardFoot}>
        <Text style={styles.cardTitle} numberOfLines={1}>
          {card.title}
        </Text>
        <Text style={styles.cardSub} numberOfLines={1}>
          {[card.category, card.regionLabel].filter(Boolean).join(" · ")}
        </Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  centered: { alignItems: "center", justifyContent: "center", gap: spacing.md },
  muted: { fontSize: 14, color: colors.sec, textAlign: "center" },
  nav: { height: 50, flexDirection: "row", alignItems: "center" },
  navButton: { width: 46, height: 46, alignItems: "center", justifyContent: "center" },
  navTitle: {
    flex: 1,
    textAlign: "center",
    fontSize: 17,
    fontWeight: "700",
    color: colors.ink,
  },
  scroll: { paddingBottom: spacing.lg },
  lead: { paddingHorizontal: PADDING, paddingTop: spacing.lg, gap: 8 },
  leadTitle: {
    fontSize: 20,
    fontWeight: "800",
    letterSpacing: -0.6,
    lineHeight: 28,
    color: colors.ink,
  },
  leadBody: { fontSize: 13.5, fontWeight: "500", color: colors.sec },
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: GUTTER,
    paddingHorizontal: PADDING,
    paddingTop: spacing.lg,
  },
  card: { borderRadius: 16, overflow: "hidden", backgroundColor: colors.inset },
  cardOn: { borderWidth: 2.5, borderColor: colors.accent },
  mark: {
    position: "absolute",
    top: 8,
    right: 8,
    width: 26,
    height: 26,
    borderRadius: 13,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.control,
    borderWidth: 1.5,
    borderColor: colors.glassBorder,
  },
  markOn: { backgroundColor: colors.accent, borderColor: colors.accent },
  cardFoot: { height: FOOTER_HEIGHT, justifyContent: "center", gap: 3, paddingHorizontal: 12 },
  cardTitle: { fontSize: 14, fontWeight: "800", letterSpacing: -0.3, color: colors.ink },
  cardSub: { fontSize: 12.5, fontWeight: "600", color: colors.sec },
  dock: {
    paddingHorizontal: PADDING,
    paddingTop: spacing.md,
    gap: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.line,
  },
  meter: { fontSize: 13, fontWeight: "600", color: colors.sec },
  error: { fontSize: 12.5, color: colors.accentText },
  submit: {
    height: 54,
    borderRadius: 8,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.accent,
  },
  submitOff: { opacity: 0.4 },
  submitText: { fontSize: 16, fontWeight: "700", color: colors.onImage },
  ghostButton: {
    paddingHorizontal: 22,
    height: 50,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.fillStrong,
  },
  ghostText: { fontSize: 15, fontWeight: "700", color: colors.ink },
});
