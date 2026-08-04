import { useCallback, useMemo, useRef, useState } from "react";
import { FlatList, Modal, Pressable, View, Text, StyleSheet } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router } from "expo-router";
import { RemoteImage } from "@/components/RemoteImage";
import { Icon } from "@/components/Icon";
import { KakaoWebMap } from "@/features/map/components/KakaoWebMap";
import { bounds, spatialSummary, type PlacedSpot } from "@/features/travel/lib/spot-geo";
import type { NearbySpot } from "@/lib/api-types";
import { colors, spacing } from "@/constants/theme";

const CARD_WIDTH = 232;
const CARD_GAP = 11;

interface Props {
  spots: PlacedSpot[];
  question: string;
  onClose: () => void;
}

export function TravelMapSheet({ spots, question, onClose }: Props) {
  const listRef = useRef<FlatList<PlacedSpot>>(null);
  const [selectedId, setSelectedId] = useState<string | null>(spots[0]?.spot.contentId ?? null);

  const pins = useMemo<NearbySpot[]>(
    () =>
      spots.map(({ spot, lat, lng }) => ({
        contentId: spot.contentId,
        title: spot.title,
        firstImageUrl: spot.imageUrl,
        addr1: spot.regionLabel,
        mapx: lng,
        mapy: lat,
        category: null,
        dist: null,
        categoryGroup: null,
        regionName: null,
        sigunguName: null,
        overview: null,
      })),
    [spots],
  );

  const center = useMemo(() => {
    if (spots.length === 0) return null;
    const lat = spots.reduce((sum, s) => sum + s.lat, 0) / spots.length;
    const lng = spots.reduce((sum, s) => sum + s.lng, 0) / spots.length;
    return { lat, lng };
  }, [spots]);

  const fit = useMemo(() => {
    const box = bounds(spots);
    return box ? { ...box, pad: { top: 96, right: 32, bottom: 132, left: 32 } } : null;
  }, [spots]);

  const summary = useMemo(() => spatialSummary(spots), [spots]);

  const select = useCallback(
    (contentId: string) => {
      setSelectedId(contentId);
      const index = spots.findIndex((s) => s.spot.contentId === contentId);
      if (index >= 0) listRef.current?.scrollToIndex({ index, animated: true, viewPosition: 0.5 });
    },
    [spots],
  );

  return (
    <Modal visible animationType="slide" presentationStyle="fullScreen" onRequestClose={onClose}>
      <View style={styles.root} testID="travel-map-sheet">
        <KakaoWebMap
          center={center}
          fit={fit}
          pins={pins}
          selectedId={selectedId}
          userLocation={null}
          onPinTap={select}
        />

        <SafeAreaView style={styles.top} edges={["top"]} pointerEvents="box-none">
          <View style={styles.topRow}>
            <Pressable
              testID="travel-map-close"
              accessibilityLabel="닫기"
              style={styles.close}
              hitSlop={6}
              onPress={onClose}
            >
              <Icon name="close" size={17} color={colors.ink} strokeWidth={2.2} />
            </Pressable>
            <View style={styles.query}>
              <Text style={styles.queryText} numberOfLines={1}>
                {question}
              </Text>
              {summary ? (
                <Text style={styles.querySummary} numberOfLines={1}>
                  {summary}
                </Text>
              ) : null}
            </View>
          </View>
        </SafeAreaView>

        <SafeAreaView style={styles.bottom} edges={["bottom"]} pointerEvents="box-none">
          <FlatList
            ref={listRef}
            horizontal
            data={spots}
            keyExtractor={(item) => item.spot.contentId}
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.strip}
            getItemLayout={(_data, index) => ({
              length: CARD_WIDTH + CARD_GAP,
              offset: (CARD_WIDTH + CARD_GAP) * index,
              index,
            })}
            renderItem={({ item }) => (
              <Pressable
                testID={`travel-map-card-${item.spot.contentId}`}
                style={[styles.card, item.spot.contentId === selectedId && styles.cardSelected]}
                onPress={() => select(item.spot.contentId)}
              >
                <RemoteImage uri={item.spot.imageUrl} style={styles.thumb} />
                <View style={styles.copy}>
                  <Text style={styles.title} numberOfLines={1}>
                    {item.spot.title}
                  </Text>
                  <Text style={styles.region} numberOfLines={1}>
                    {item.spot.regionLabel}
                  </Text>
                  {item.spot.tag ? (
                    <View style={styles.tag}>
                      <Text style={styles.tagText}>{item.spot.tag}</Text>
                    </View>
                  ) : null}
                </View>
                <Pressable
                  testID={`travel-map-detail-${item.spot.contentId}`}
                  accessibilityLabel="상세 보기"
                  hitSlop={8}
                  onPress={() => {
                    onClose();
                    router.push(`/spots/${item.spot.contentId}`);
                  }}
                >
                  <Icon name="chevron-right" size={16} color={colors.ter} strokeWidth={2.1} />
                </Pressable>
              </Pressable>
            )}
          />
        </SafeAreaView>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.inset },
  top: { position: "absolute", top: 0, left: 0, right: 0 },
  topRow: { flexDirection: "row", alignItems: "center", gap: 9, padding: spacing.md },
  close: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: colors.bg,
    borderWidth: 1,
    borderColor: colors.line,
    alignItems: "center",
    justifyContent: "center",
  },
  query: {
    flex: 1,
    minHeight: 38,
    justifyContent: "center",
    paddingVertical: 6,
    paddingHorizontal: 14,
    borderRadius: 19,
    backgroundColor: colors.bg,
    borderWidth: 1,
    borderColor: colors.line,
  },
  queryText: { fontSize: 12.5, fontWeight: "800", letterSpacing: -0.2, color: colors.ink },
  querySummary: { marginTop: 1, fontSize: 11, color: colors.ter },
  bottom: { position: "absolute", left: 0, right: 0, bottom: 0 },
  strip: { gap: CARD_GAP, paddingHorizontal: spacing.md, paddingBottom: spacing.md },
  card: {
    width: CARD_WIDTH,
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    padding: 10,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.bg,
  },
  cardSelected: { borderColor: colors.accent, borderWidth: 2 },
  thumb: { width: 52, height: 52, borderRadius: 9, backgroundColor: colors.skeleton },
  copy: { flex: 1, minWidth: 0 },
  title: { fontSize: 13, fontWeight: "800", letterSpacing: -0.3, color: colors.ink },
  region: { marginTop: 2, fontSize: 11, color: colors.ter },
  tag: {
    alignSelf: "flex-start",
    marginTop: 5,
    paddingVertical: 2,
    paddingHorizontal: 6,
    borderRadius: 5,
    backgroundColor: colors.accentFill,
  },
  tagText: { fontSize: 10, fontWeight: "800", color: colors.accentText },
});
