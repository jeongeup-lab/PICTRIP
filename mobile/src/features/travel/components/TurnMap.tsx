import { useMemo } from "react";
import { Pressable, View, Text, StyleSheet } from "react-native";
import Svg, { Circle, Path, Rect } from "react-native-svg";
import { Icon } from "@/components/Icon";
import { previewPoints, spatialSummary, type PlacedSpot } from "@/features/travel/lib/spot-geo";
import { colors } from "@/constants/theme";

export const OPEN_MAP_LABEL = "지도에서 보기";

const PREVIEW = { width: 300, height: 108, padding: 18 };

interface Props {
  spots: PlacedSpot[];
  onOpen: () => void;
}

export function TurnMap({ spots, onOpen }: Props) {
  const points = useMemo(() => previewPoints(spots, PREVIEW), [spots]);
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
      <Svg
        width="100%"
        height={PREVIEW.height}
        viewBox={`0 0 ${PREVIEW.width} ${PREVIEW.height}`}
        preserveAspectRatio="none"
      >
        <Rect x="0" y="0" width={PREVIEW.width} height={PREVIEW.height} fill="#EEF1EF" />
        <Path
          d={`M-10 ${PREVIEW.height - 22} Q70 ${PREVIEW.height - 34} 150 ${PREVIEW.height - 26} T${PREVIEW.width + 10} ${PREVIEW.height - 32}`}
          stroke="#DCE6E1"
          strokeWidth={16}
          fill="none"
        />
        <Path
          d={`M-10 34 Q90 18 190 32 T${PREVIEW.width + 10} 22`}
          stroke="#E3EBE6"
          strokeWidth={12}
          fill="none"
        />
        {points.map((point, index) => (
          <Circle
            key={point.contentId}
            cx={point.x}
            cy={point.y}
            r={index === 0 ? 7 : 5.5}
            fill={index === 0 ? colors.accent : colors.ink}
            stroke="#FFFFFF"
            strokeWidth={2}
          />
        ))}
      </Svg>

      <View style={styles.bar}>
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
  bar: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderTopWidth: 1,
    borderTopColor: colors.line,
    backgroundColor: colors.bg,
  },
  summary: { flex: 1, fontSize: 12.5, fontWeight: "600", letterSpacing: -0.2, color: colors.sec },
  open: { fontSize: 12, fontWeight: "800", letterSpacing: -0.2, color: colors.accentText },
});
