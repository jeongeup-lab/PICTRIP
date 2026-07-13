import { View, Text, Pressable, StyleSheet } from "react-native";
import { Icon } from "@/components/Icon";
import { useSaveOptimistic } from "@/features/saved/hooks/use-save-optimistic";
import type { ChannelCard } from "@/features/channels/api";
import { colors } from "@/constants/theme";

interface Props {
  card: ChannelCard;
  onDetail: () => void;
}

function SaveActions({ contentId, onDetail }: { contentId: string; onDetail: () => void }) {
  const { saved, toggle } = useSaveOptimistic(contentId);
  return (
    <View style={styles.actions}>
      <Pressable testID="story-save" style={styles.save} onPress={toggle} hitSlop={8}>
        <Icon
          name={saved ? "bookmark-fill" : "bookmark"}
          size={20}
          color={colors.onImage}
          strokeWidth={1.8}
        />
        <Text style={styles.saveText}>저장</Text>
      </Pressable>
      <Pressable testID="story-detail" style={styles.detail} onPress={onDetail}>
        <Text style={styles.detailText}>자세히 보기</Text>
      </Pressable>
    </View>
  );
}

export function StoryCard({ card, onDetail }: Props) {
  const hasBadges = card.rank !== null || card.dday !== null || card.tag !== null;

  return (
    <View style={styles.root}>
      {hasBadges ? (
        <View style={styles.badges}>
          {card.rank !== null ? (
            <View style={styles.rank}>
              <Text style={styles.rankText}>{card.rank}</Text>
            </View>
          ) : null}
          {card.dday !== null ? (
            <View style={styles.dday}>
              <Text style={styles.ddayText}>{card.dday}</Text>
            </View>
          ) : null}
          {card.tag !== null ? (
            <View style={styles.tag}>
              <Text style={styles.tagText}>{card.tag}</Text>
            </View>
          ) : null}
        </View>
      ) : null}

      <Text testID="story-card-title" style={styles.name}>
        {card.title}
      </Text>
      {card.regionLabel ? <Text style={styles.region}>{card.regionLabel}</Text> : null}
      {card.line ? <Text style={styles.line}>{card.line}</Text> : null}

      {card.saveable && card.contentId ? (
        <SaveActions contentId={card.contentId} onDetail={onDetail} />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { gap: 12 },
  badges: { flexDirection: "row", alignItems: "center", gap: 8 },
  rank: {
    width: 38,
    height: 38,
    borderRadius: 19,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.glassFill,
    borderWidth: 1,
    borderColor: colors.glassBorder,
  },
  rankText: { fontSize: 17, fontWeight: "800", color: colors.onImage },
  dday: {
    height: 26,
    paddingHorizontal: 12,
    borderRadius: 13,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.accent,
  },
  ddayText: { fontSize: 12.5, fontWeight: "800", color: colors.onImage },
  tag: {
    height: 26,
    paddingHorizontal: 12,
    borderRadius: 13,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.glassFill,
    borderWidth: 1,
    borderColor: colors.glassBorder,
  },
  tagText: { fontSize: 12.5, fontWeight: "700", color: colors.onImage },
  name: { fontSize: 26, fontWeight: "800", letterSpacing: -0.5, color: colors.onImage },
  region: { fontSize: 14, fontWeight: "600", color: colors.onDim },
  line: { fontSize: 13.5, lineHeight: 20, fontWeight: "600", color: colors.onImage },
  actions: { flexDirection: "row", alignItems: "center", gap: 10, marginTop: 4 },
  save: {
    flexDirection: "row",
    alignItems: "center",
    gap: 7,
    height: 48,
    paddingHorizontal: 18,
    borderRadius: 24,
    backgroundColor: colors.glassFill,
    borderWidth: 1,
    borderColor: colors.glassBorder,
  },
  saveText: { fontSize: 15, fontWeight: "700", color: colors.onImage },
  detail: {
    flex: 1,
    height: 48,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 24,
    backgroundColor: colors.onImage,
  },
  detailText: { fontSize: 15, fontWeight: "800", color: colors.ink },
});
