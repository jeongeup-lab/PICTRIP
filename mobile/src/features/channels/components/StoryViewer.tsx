import { useEffect, useState } from "react";
import {
  View,
  Text,
  Pressable,
  PanResponder,
  StyleSheet,
  ActivityIndicator,
  useWindowDimensions,
} from "react-native";
import Svg, { Defs, LinearGradient, Stop, Rect } from "react-native-svg";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router } from "expo-router";
import { Image } from "expo-image";
import { Icon } from "@/components/Icon";
import { RemoteImage, fullSizeSourceUri } from "@/components/RemoteImage";
import { useChannelCards, useChannels, useSeenChannels } from "@/features/channels/queries";
import type { ChannelKey } from "@/features/channels/api";
import { StoryCard } from "@/features/channels/components/StoryCard";
import { prefetchSpot } from "@/features/spots/queries";
import { colors } from "@/constants/theme";

interface Props {
  start: ChannelKey;
}

const LAST = Number.MAX_SAFE_INTEGER;
const BG = "#141216";
const CARD_HEIGHT = 520;

export function StoryViewer({ start }: Props) {
  const insets = useSafeAreaInsets();
  const { width } = useWindowDimensions();
  const cardWidth = width - 32;
  const { data: channelData, isError: channelsError } = useChannels();
  const { markSeen } = useSeenChannels();
  const channels = (channelData?.channels ?? []).filter((c) => c.available);

  const [manualIdx, setManualIdx] = useState<number | null>(null);
  const [cardIdx, setCardIdx] = useState(0);

  const startIdx = Math.max(
    0,
    channels.findIndex((c) => c.key === start),
  );
  const channelIdx = manualIdx ?? startIdx;
  const channel = channels[channelIdx];
  const channelKey = channel?.key ?? start;

  const { data: cardData, isError } = useChannelCards(channelKey);
  const noData = !cardData;
  const cards = cardData?.cards ?? [];
  const cardCount = cards.length;
  const shownIdx = cardCount > 0 ? Math.min(cardIdx, cardCount - 1) : 0;
  const currentCard = cards[shownIdx];

  useEffect(() => {
    for (const c of (cardData?.cards ?? []).slice(shownIdx + 1, shownIdx + 3)) {
      if (c.imageUrl)
        void Image.prefetch(fullSizeSourceUri(c.imageUrl), { cachePolicy: "memory-disk" });
    }
  }, [cardData, shownIdx]);

  const close = () => router.back();

  const nextChannel = () => {
    markSeen(channelKey);
    if (channelIdx < channels.length - 1) {
      setManualIdx(channelIdx + 1);
      setCardIdx(0);
    } else {
      close();
    }
  };

  const prevChannel = () => {
    if (channelIdx > 0) {
      setManualIdx(channelIdx - 1);
      setCardIdx(LAST);
    }
  };

  const rightTap = () => {
    if (noData) return;
    if (shownIdx < cardCount - 1) setCardIdx(shownIdx + 1);
    else nextChannel();
  };

  const leftTap = () => {
    if (noData) return;
    if (shownIdx > 0) setCardIdx(shownIdx - 1);
    else prevChannel();
  };

  const onDetail = () => {
    const contentId = currentCard?.contentId;
    if (!contentId) return;
    prefetchSpot({ ...currentCard, contentId });
    close();
    router.push(`/spots/${contentId}`);
  };

  const pan = PanResponder.create({
    onMoveShouldSetPanResponder: (_e, g) => Math.abs(g.dx) > 12 || g.dy > 12,
    onPanResponderRelease: (_e, g) => {
      if (g.dy > 90 && g.dy > Math.abs(g.dx)) close();
      else if (noData) return;
      else if (g.dx < -50) nextChannel();
      else if (g.dx > 50) prevChannel();
    },
  });

  if (channels.length === 0) {
    return (
      <View style={[styles.root, styles.errorRoot, { backgroundColor: BG }]} {...pan.panHandlers}>
        {channelsError ? (
          <Text style={styles.loadingText}>채널을 불러오지 못했어요</Text>
        ) : channelData ? (
          <Text style={styles.loadingText}>지금은 열 수 있는 채널이 없어요</Text>
        ) : (
          <>
            <ActivityIndicator color={colors.onImage} />
            <Text style={styles.loadingText}>채널을 불러오는 중이에요</Text>
          </>
        )}
        <Pressable
          testID="story-empty-close"
          style={[styles.close, styles.closeFloat, { top: insets.top + 12 }]}
          onPress={close}
          hitSlop={8}
        >
          <Icon name="close" size={18} color={colors.onImage} />
        </Pressable>
      </View>
    );
  }

  if (isError) {
    return (
      <View style={[styles.root, styles.errorRoot, { backgroundColor: BG }]} {...pan.panHandlers}>
        <Text style={styles.errorText}>채널을 불러오지 못했어요</Text>
        <Pressable
          style={[styles.close, styles.closeFloat, { top: insets.top + 12 }]}
          onPress={close}
          hitSlop={8}
        >
          <Icon name="close" size={18} color={colors.onImage} />
        </Pressable>
      </View>
    );
  }

  return (
    <View style={[styles.root, { backgroundColor: BG }]} {...pan.panHandlers}>
      <View style={styles.cardWrap} pointerEvents="none">
        <View style={[styles.card, { width: cardWidth, height: CARD_HEIGHT }]}>
          <RemoteImage uri={currentCard?.imageUrl ?? null} style={StyleSheet.absoluteFill} />
          <Svg style={StyleSheet.absoluteFill} width="100%" height="100%" pointerEvents="none">
            <Defs>
              <LinearGradient id="storyCardScrim" x1="0" y1="0" x2="0" y2="1">
                <Stop offset="0" stopColor={BG} stopOpacity={0.28} />
                <Stop offset="0.5" stopColor={BG} stopOpacity={0.05} />
                <Stop offset="1" stopColor={BG} stopOpacity={0.78} />
              </LinearGradient>
            </Defs>
            <Rect x="0" y="0" width="100%" height="100%" fill="url(#storyCardScrim)" />
          </Svg>
        </View>
      </View>

      <Pressable
        testID="story-tap-left"
        style={[StyleSheet.absoluteFill, styles.zoneLeft]}
        onPress={leftTap}
      />
      <Pressable
        testID="story-tap-right"
        style={[StyleSheet.absoluteFill, styles.zoneRight]}
        onPress={rightTap}
      />

      <View style={[styles.top, { paddingTop: insets.top + 12 }]} pointerEvents="box-none">
        <View style={styles.progress}>
          {cards.map((_, i) => (
            <View key={i} testID="story-progress-seg" style={styles.segTrack}>
              <View
                style={[
                  styles.segFill,
                  { opacity: i < shownIdx ? 1 : i === shownIdx ? 0.55 : 0.32 },
                ]}
              />
            </View>
          ))}
        </View>
        <View style={styles.topRow}>
          <Text style={styles.channelLabel}>{channel?.label ?? ""}</Text>
          <Pressable style={styles.close} onPress={close} hitSlop={8}>
            <Icon name="close" size={18} color={colors.onImage} />
          </Pressable>
        </View>
      </View>

      <View style={styles.cardWrap} pointerEvents="box-none">
        <View
          style={[styles.cardMeta, { width: cardWidth, height: CARD_HEIGHT }]}
          pointerEvents="box-none"
        >
          {currentCard ? (
            <StoryCard
              key={currentCard.contentId ?? String(shownIdx)}
              card={currentCard}
              onDetail={onDetail}
            />
          ) : null}
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  cardWrap: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    alignItems: "center",
    justifyContent: "center",
  },
  card: {
    borderRadius: 16,
    overflow: "hidden",
    backgroundColor: colors.sec,
  },
  cardMeta: {
    justifyContent: "flex-end",
    paddingHorizontal: 20,
    paddingBottom: 22,
  },
  errorRoot: { alignItems: "center", justifyContent: "center", paddingHorizontal: 24 },
  errorText: { fontSize: 15, fontWeight: "600", color: colors.onImage, textAlign: "center" },
  loadingText: { fontSize: 14, fontWeight: "500", color: colors.onImage, textAlign: "center" },
  zoneLeft: { right: "66%" },
  zoneRight: { left: "34%" },
  top: { position: "absolute", top: 0, left: 0, right: 0, paddingHorizontal: 16 },
  progress: { flexDirection: "row", gap: 4 },
  segTrack: {
    flex: 1,
    height: 3,
    borderRadius: 2,
    overflow: "hidden",
    backgroundColor: "rgba(255,255,255,0.28)",
  },
  segFill: { flex: 1, backgroundColor: colors.onImage },
  topRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: 14,
  },
  channelLabel: { fontSize: 16, fontWeight: "800", color: colors.onImage },
  close: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.glassFill,
    borderWidth: 1,
    borderColor: colors.glassBorder,
  },
  closeFloat: { position: "absolute", right: 16 },
});
