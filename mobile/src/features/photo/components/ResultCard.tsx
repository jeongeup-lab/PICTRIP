import { Pressable, View, Text, StyleSheet } from "react-native";
import { RemoteImage } from "@/components/RemoteImage";
import { SimilarityGauge } from "@/features/photo/components/SimilarityGauge";
import { formatDistance } from "@/lib/distance";
import type { PhotoMatch } from "@/lib/api-types";
import { colors, radii } from "@/constants/theme";

interface Props {
  match: PhotoMatch;
  showDistance: boolean;
  onPress: () => void;
}

export function ResultCard({ match, showDistance, onPress }: Props) {
  const region = [match.regionName, match.sigunguName].filter(Boolean).join(" ");
  const parts: string[] = [];
  if (match.category) parts.push(match.category);
  if (region) parts.push(region);
  if (showDistance && match.distance != null) parts.push(formatDistance(match.distance));
  const meta = parts.join(" · ");

  return (
    <Pressable onPress={onPress} style={styles.card}>
      <RemoteImage uri={match.firstImageUrl} radius={radii.xl} style={styles.image} />
      <View style={styles.bar}>
        <View style={styles.tx}>
          <Text numberOfLines={1} style={styles.name}>
            {match.title}
          </Text>
          {meta ? (
            <Text numberOfLines={1} style={styles.meta}>
              {meta}
            </Text>
          ) : null}
        </View>
        <SimilarityGauge similarity={match.similarity} />
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: { height: 188, borderRadius: radii.xl, overflow: "hidden", backgroundColor: colors.inset },
  image: { width: "100%", height: "100%" },
  bar: {
    position: "absolute",
    left: 12,
    right: 12,
    bottom: 12,
    borderRadius: 15,
    paddingHorizontal: 16,
    paddingVertical: 10,
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
    backgroundColor: colors.scrim,
    borderWidth: 1,
    borderColor: colors.glassBorder,
  },
  tx: { flex: 1, minWidth: 0 },
  name: { fontSize: 17, fontWeight: "700", color: colors.onImage },
  meta: { fontSize: 12.5, color: colors.onDim, marginTop: 2 },
});
