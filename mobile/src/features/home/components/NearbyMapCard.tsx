import { useCallback, useMemo, useState } from "react";
import { Modal, Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Icon } from "@/components/Icon";
import { RemoteImage } from "@/components/RemoteImage";
import { KakaoWebMap } from "@/features/map/components/KakaoWebMap";
import { bounds, center, countsOf, pinsFrom, placed } from "@/features/home/lib/map-pins";
import type { HomeSpotCard } from "@/features/home/api";
import type { LatLng } from "@/features/map/lib/geo";
import { colors, radii, spacing } from "@/constants/theme";

export const MAP_HEIGHT = 206;
export const EMPTY_TITLE = "지도에 표시할 장소가 없어요";
const MAP_PAD = 42;

interface Props {
  title: string;
  cards: HomeSpotCard[];
  origin: LatLng | null;
  onOpenSpot: (contentId: string) => void;
}

export function NearbyMapCard({ title, cards, origin, onOpenSpot }: Props) {
  const [open, setOpen] = useState(false);
  const [pickedId, setPickedId] = useState<string | null>(null);

  const spots = useMemo(() => placed(cards), [cards]);
  const pins = useMemo(() => pinsFrom(spots), [spots]);
  const mapCenter = useMemo(() => center(spots), [spots]);
  const fit = useMemo(() => {
    const box = bounds(spots);
    if (!box) return null;
    return { ...box, pad: { top: MAP_PAD, right: MAP_PAD, bottom: MAP_PAD, left: MAP_PAD } };
  }, [spots]);
  const counts = useMemo(() => countsOf(cards), [cards]);
  const picked = cards.find((card) => card.contentId === pickedId) ?? null;

  const close = useCallback(() => {
    setOpen(false);
    setPickedId(null);
  }, []);

  if (spots.length === 0) return null;

  return (
    <>
      <Pressable
        testID="home-map-card"
        accessibilityRole="button"
        accessibilityLabel={`${title} 지도로 보기`}
        style={({ pressed }) => [styles.card, pressed && styles.pressed]}
        onPress={() => setOpen(true)}
      >
        <View style={styles.mapSlot} pointerEvents="none">
          <KakaoWebMap
            center={mapCenter}
            fit={fit}
            pins={pins}
            userLocation={origin}
            interactive={false}
            onPinTap={() => undefined}
          />
        </View>
        <View style={styles.overlay}>
          <View style={styles.overlayCopy}>
            <Text style={styles.overlayTitle}>{title}</Text>
            <Text style={styles.overlayNote}>
              카페 {counts.cafe} · 명소 {counts.spot} · 맛집 {counts.food}
            </Text>
          </View>
          <View style={styles.overlayGo}>
            <Icon name="map-pin" size={17} color={colors.onImage} strokeWidth={1.9} />
          </View>
        </View>
      </Pressable>

      <Modal visible={open} animationType="slide" onRequestClose={close}>
        <SafeAreaView style={styles.sheet} edges={["top"]}>
          <View style={styles.sheetHead}>
            <Text style={styles.sheetTitle}>{title}</Text>
            <Pressable
              testID="home-map-close"
              accessibilityRole="button"
              accessibilityLabel="지도 닫기"
              hitSlop={8}
              onPress={close}
            >
              <Icon name="close" size={20} color={colors.ink} strokeWidth={2} />
            </Pressable>
          </View>

          <View style={styles.sheetMap}>
            <KakaoWebMap
              center={mapCenter}
              fit={fit}
              pins={pins}
              selectedId={pickedId}
              userLocation={origin}
              onPinTap={setPickedId}
              onBlankTap={() => setPickedId(null)}
            />
            {picked ? (
              <Pressable
                testID="home-map-picked"
                accessibilityRole="button"
                accessibilityLabel={`${picked.title} 상세보기`}
                style={({ pressed }) => [styles.picked, pressed && styles.pressed]}
                onPress={() => {
                  close();
                  onOpenSpot(picked.contentId);
                }}
              >
                <RemoteImage uri={picked.imageUrl} style={styles.pickedImage} radius={12} midSize />
                <View style={styles.pickedCopy}>
                  <Text style={styles.pickedTitle} numberOfLines={1}>
                    {picked.title}
                  </Text>
                  <Text style={styles.pickedNote} numberOfLines={1}>
                    {[picked.category, picked.regionLabel].filter(Boolean).join(" · ")}
                  </Text>
                </View>
                <Icon name="chevron-right" size={18} color={colors.ter} strokeWidth={2} />
              </Pressable>
            ) : null}
          </View>
        </SafeAreaView>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  card: {
    marginHorizontal: spacing.lg,
    height: MAP_HEIGHT,
    borderRadius: 18,
    overflow: "hidden",
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.inset,
  },
  mapSlot: { position: "absolute", top: 0, right: 0, bottom: 0, left: 0 },
  overlay: {
    position: "absolute",
    left: 10,
    right: 10,
    bottom: 10,
    height: 52,
    borderRadius: 14,
    flexDirection: "row",
    alignItems: "center",
    gap: 11,
    paddingHorizontal: 14,
    backgroundColor: colors.glassFill,
    borderWidth: 1,
    borderColor: colors.glassBorder,
  },
  overlayCopy: { flex: 1, minWidth: 0 },
  overlayTitle: { fontSize: 14, fontWeight: "800", letterSpacing: -0.3, color: colors.ink },
  overlayNote: { marginTop: 1, fontSize: 11.5, fontWeight: "600", color: colors.sec },
  overlayGo: {
    width: 32,
    height: 32,
    borderRadius: radii.pill,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.ink,
  },
  sheet: { flex: 1, backgroundColor: colors.bg },
  sheetHead: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.md,
  },
  sheetTitle: { fontSize: 19, fontWeight: "800", letterSpacing: -0.5, color: colors.ink },
  sheetMap: { flex: 1 },
  picked: {
    position: "absolute",
    left: spacing.md,
    right: spacing.md,
    bottom: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    padding: 12,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.bg,
  },
  pickedImage: { width: 60, height: 60 },
  pickedCopy: { flex: 1, minWidth: 0 },
  pickedTitle: { fontSize: 15, fontWeight: "800", letterSpacing: -0.35, color: colors.ink },
  pickedNote: { marginTop: 2, fontSize: 12.5, fontWeight: "600", color: colors.sec },
  pressed: { opacity: 0.85 },
});
