import { Pressable, View, Text, StyleSheet } from "react-native";
import { RemoteImage } from "@/components/RemoteImage";
import { Icon } from "@/components/Icon";
import type { PhotoMatch } from "@/features/plan/api";
import { shortRegion } from "@/features/plan/lib/plan-format";
import { colors, radii } from "@/constants/theme";

interface Props {
  match: PhotoMatch;
  rank: number;
  selected: boolean;
  onPress: () => void;
}

export function MatchCard({ match, rank, selected, onPress }: Props) {
  return (
    <Pressable
      testID={`match-${match.contentId}`}
      style={({ pressed }) => [styles.card, pressed && styles.pressed]}
      onPress={onPress}
    >
      <View style={[styles.frame, selected && styles.frameSelected]}>
        <RemoteImage uri={match.imageUrl} style={styles.image} radius={radii.lg} />
        <View style={styles.rank}>
          <Text style={styles.rankText}>{rank}</Text>
        </View>
        <View style={[styles.check, selected && styles.checkSelected]}>
          <Icon name="check" size={13} color={colors.onImage} strokeWidth={2.2} />
        </View>
      </View>
      <Text style={styles.title} numberOfLines={1}>
        {match.title}
      </Text>
      <Text style={styles.meta} numberOfLines={1}>
        {shortRegion(match.address)} · <Text style={styles.score}>{similarityLabel(match)}</Text>
      </Text>
    </Pressable>
  );
}

function similarityLabel(match: PhotoMatch): string {
  return `${Math.round(match.similarity * 100)}%`;
}

const styles = StyleSheet.create({
  card: { width: "48%" },
  pressed: { opacity: 0.75 },
  frame: {
    borderRadius: radii.lg + 2,
    borderWidth: 2,
    borderColor: "transparent",
    padding: 1.5,
  },
  frameSelected: { borderColor: colors.ink },
  image: { height: 112 },
  rank: {
    position: "absolute",
    top: 8,
    left: 8,
    height: 26,
    minWidth: 26,
    paddingHorizontal: 8,
    borderRadius: 13,
    backgroundColor: colors.control,
    alignItems: "center",
    justifyContent: "center",
  },
  rankText: { fontSize: 12.5, fontWeight: "700", color: colors.onImage },
  check: {
    position: "absolute",
    top: 8,
    right: 8,
    width: 26,
    height: 26,
    borderRadius: 13,
    backgroundColor: colors.control,
    alignItems: "center",
    justifyContent: "center",
    opacity: 0.55,
  },
  checkSelected: { backgroundColor: colors.ink, opacity: 1 },
  title: {
    marginTop: 9,
    fontSize: 13.5,
    fontWeight: "700",
    letterSpacing: -0.2,
    color: colors.ink,
  },
  meta: { marginTop: 2.5, fontSize: 12, color: colors.ter },
  score: { color: colors.accentText, fontWeight: "700" },
});
