import { useState } from "react";
import {
  ActivityIndicator,
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
import { useSaveMutation } from "@/features/saved/queries";
import { queryClient } from "@/lib/query-client";
import { colors, spacing } from "@/constants/theme";

const MIN_SAVES = 3;
const BG = "#141216";

export function TastePicker() {
  const insets = useSafeAreaInsets();
  const { width, height } = useWindowDimensions();
  const { data, isLoading, isError } = useTastePicks();
  const saveMut = useSaveMutation();

  const [index, setIndex] = useState(0);
  const [savedIds, setSavedIds] = useState<string[]>([]);

  const cards = data?.items ?? [];
  const card = cards[index];
  const done = cards.length > 0 && index >= cards.length;
  const enough = savedIds.length >= MIN_SAVES;

  const close = () => {
    void queryClient.invalidateQueries({ queryKey: ["home-recommendations"] });
    router.back();
  };

  const advance = () => setIndex((i) => i + 1);

  const keep = () => {
    if (!card) return;
    setSavedIds((ids) => (ids.includes(card.contentId) ? ids : [...ids, card.contentId]));
    saveMut.mutate(card.contentId);
    advance();
  };

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
            <View style={[styles.card, { width: cardWidth, height: cardHeight }]}>
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
              <View style={styles.cardMeta}>
                <Text style={styles.cardTitle} numberOfLines={2}>
                  {card.title}
                </Text>
                <Text style={styles.cardRegion} numberOfLines={1}>
                  {[card.category, card.regionLabel].filter(Boolean).join(" · ")}
                </Text>
              </View>
            </View>
          </View>

          <View style={[styles.actions, { paddingBottom: insets.bottom + spacing.lg }]}>
            <Pressable testID="taste-skip" onPress={advance} style={styles.skip}>
              <Icon name="close" size={24} color={colors.sec} />
            </Pressable>
            <Pressable testID="taste-keep" onPress={keep} style={styles.keep}>
              <Icon name="star-fill" size={26} color={colors.onImage} />
              <Text style={styles.keepText}>저장</Text>
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
  cardMeta: { position: "absolute", left: 20, right: 20, bottom: 20, gap: 4 },
  cardTitle: { fontSize: 22, fontWeight: "800", letterSpacing: -0.6, color: colors.onImage },
  cardRegion: { fontSize: 13.5, fontWeight: "600", color: colors.onDim },
  actions: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 14 },
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
