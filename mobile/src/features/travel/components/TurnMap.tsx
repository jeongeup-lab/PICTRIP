import { useMemo } from "react";
import { Pressable, View, Text, StyleSheet } from "react-native";
import { Icon } from "@/components/Icon";
import { KakaoWebMap } from "@/features/map/components/KakaoWebMap";
import {
  bounds,
  center,
  miniFitSpots,
  pinsFrom,
  spatialSummary,
  type PlacedSpot,
} from "@/features/travel/lib/spot-geo";
import { colors } from "@/constants/theme";

export const OPEN_MAP_LABEL = "지도에서 보기";

const MAP_HEIGHT = 200;
const FIT_PAD = { top: 18, right: 18, bottom: 18, left: 18 };

interface Props {
  spots: PlacedSpot[];
  live: boolean;
  selectedId?: string | null;
  onOpen: () => void;
}

export function TurnMap({ spots, live, selectedId = null, onOpen }: Props) {
  const pins = useMemo(() => pinsFrom(spots), [spots]);
  const framed = useMemo(() => miniFitSpots(spots), [spots]);
  const fit = useMemo(() => {
    const box = bounds(framed);
    return box ? { ...box, pad: FIT_PAD } : null;
  }, [framed]);
  const focus = useMemo(() => {
    const picked = spots.find((s) => s.spot.contentId === selectedId);
    return picked ? { lat: picked.lat, lng: picked.lng } : center(framed);
  }, [spots, framed, selectedId]);
  const summary = useMemo(() => spatialSummary(spots), [spots]);

  if (spots.length === 0) return null;

  return (
    <Pressable
      testID="travel-turn-map"
      accessibilityRole="button"
      accessibilityLabel={OPEN_MAP_LABEL}
      style={({ pressed }) => [styles.card, pressed && styles.pressed]}
      onPress={onOpen}
    >
      {live ? (
        <View style={styles.map} pointerEvents="none">
          <KakaoWebMap
            center={focus}
            fit={fit}
            pins={pins}
            selectedId={selectedId}
            userLocation={null}
            interactive={false}
            accentPins
            onPinTap={() => undefined}
          />
        </View>
      ) : null}

      <View style={[styles.bar, live && styles.barUnderMap]}>
        <Text style={styles.summary} numberOfLines={1}>
          {summary ?? `지도에 ${spots.length}곳`}
        </Text>
        <Text style={styles.open}>{OPEN_MAP_LABEL}</Text>
        <Icon name="chevron-right" size={13} color={colors.accentText} strokeWidth={2.2} />
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    marginTop: 13,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: 14,
    overflow: "hidden",
    backgroundColor: colors.inset,
  },
  pressed: { opacity: 0.9 },
  map: { height: MAP_HEIGHT },
  bar: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingVertical: 10,
    paddingHorizontal: 12,
    backgroundColor: colors.bg,
  },
  barUnderMap: { borderTopWidth: 1, borderTopColor: colors.line },
  summary: { flex: 1, fontSize: 12.5, fontWeight: "600", letterSpacing: -0.2, color: colors.sec },
  open: { fontSize: 12, fontWeight: "800", letterSpacing: -0.2, color: colors.accentText },
});
