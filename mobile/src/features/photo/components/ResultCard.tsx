import { Pressable, View, Text, StyleSheet } from "react-native";
import { RemoteImage } from "@/components/RemoteImage";
import { Icon } from "@/components/Icon";
import { formatDistance } from "@/lib/distance";
import type { PhotoMatch } from "@/lib/api-types";
import { colors, radii } from "@/constants/theme";
import { useDiscoverySave } from "@/features/saved/hooks/use-discovery-save";

interface Props {
  match: PhotoMatch;
  showDistance: boolean;
  onPress: () => void;
  rank?: number;
  showBest?: boolean;
  isLast?: boolean;
}

export function ResultCard({
  match,
  showDistance,
  onPress,
  rank = -1,
  showBest = true,
  isLast = false,
}: Props) {
  const region = [match.regionName, match.sigunguName].filter(Boolean).join(" ");
  const parts: string[] = [];
  if (match.category) parts.push(match.category);
  if (region) parts.push(region);
  if (showDistance && match.distance != null) parts.push(formatDistance(match.distance));
  const meta = parts.join(" · ");

  const percent = Math.round(match.similarity * 100);
  const isHigh = percent >= 85;
  const { saved, toggle } = useDiscoverySave(match);

  return (
    <Pressable onPress={onPress} style={[styles.row, isLast && styles.rowLast]}>
      <View style={styles.thumbWrap}>
        <RemoteImage uri={match.firstImageUrl} radius={radii.md} style={styles.thumb} />
        {rank === 0 && showBest ? (
          <View style={styles.best}>
            <Text style={styles.bestText}>BEST</Text>
          </View>
        ) : null}
        <Pressable style={styles.heart} onPress={toggle} hitSlop={8}>
          <Icon name={saved ? "heart-fill" : "heart"} size={14} color={colors.onImage} />
        </Pressable>
      </View>

      <View style={styles.body}>
        <Text numberOfLines={1} style={styles.name}>
          {match.title}
        </Text>
        {meta ? (
          <Text numberOfLines={1} style={styles.meta}>
            {meta}
          </Text>
        ) : null}
      </View>

      <View style={styles.simCol}>
        <Text
          style={[styles.simPct, isHigh ? styles.simHigh : styles.simInk]}
        >{`${percent}%`}</Text>
        <Text style={styles.simLabel}>유사도</Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.fillStrong,
  },
  rowLast: { borderBottomWidth: 0 },
  thumbWrap: { width: 96, height: 96, flexShrink: 0 },
  thumb: { width: 96, height: 96 },
  best: {
    position: "absolute",
    left: 6,
    top: 6,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: radii.sm,
    backgroundColor: colors.accent,
  },
  bestText: { fontSize: 10, fontWeight: "800", color: colors.onImage },
  heart: {
    position: "absolute",
    top: 6,
    right: 6,
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: colors.control,
    alignItems: "center",
    justifyContent: "center",
  },
  body: { flex: 1, minWidth: 0 },
  name: { fontSize: 16, fontWeight: "700", color: colors.ink },
  meta: { fontSize: 12.5, color: colors.ter, marginTop: 4 },
  simCol: { alignItems: "flex-end", flexShrink: 0 },
  simPct: { fontSize: 19, fontWeight: "800" },
  simHigh: { color: colors.accentText },
  simInk: { color: colors.ink },
  simLabel: { fontSize: 10.5, fontWeight: "600", color: colors.ter, marginTop: 1 },
});
