import { Pressable, View, Text, StyleSheet } from "react-native";
import { RemoteImage } from "@/components/RemoteImage";
import { Icon } from "@/components/Icon";
import { colors, radii, spacing } from "@/constants/theme";
import type { ChatCard } from "@/features/chat/types";
import { useDiscoverySave } from "@/features/saved/hooks/use-discovery-save";
import type { SpotCard } from "@/lib/api-types";

interface Props {
  card: ChatCard;
  onPress: () => void;
  onPressIn?: () => void;
}

export function ChatSpotCard({ card, onPress, onPressIn }: Props) {
  const meta = [card.regionLabel, card.category].filter(Boolean).join(" · ");
  const spotCard: SpotCard = {
    contentId: card.contentId,
    title: card.title,
    firstImageUrl: card.firstImageUrl,
    category: card.category,
    addr1: card.regionLabel,
  };
  const { saved, toggle } = useDiscoverySave(spotCard);
  return (
    <Pressable style={styles.card} onPress={onPress} onPressIn={onPressIn}>
      <View>
        <RemoteImage uri={card.firstImageUrl} radius={radii.md} style={styles.img} />
        {card.quiet ? (
          <View style={styles.quiet}>
            <Text style={styles.quietText}>지금 한산</Text>
          </View>
        ) : null}
        <Pressable style={styles.heart} onPress={toggle} hitSlop={8}>
          <Icon name={saved ? "heart-fill" : "heart"} size={14} color={colors.onImage} />
        </Pressable>
      </View>
      <Text numberOfLines={1} style={styles.title}>
        {card.title}
      </Text>
      {meta ? (
        <Text numberOfLines={1} style={styles.meta}>
          {meta}
        </Text>
      ) : null}
      {card.why ? (
        <Text numberOfLines={2} style={styles.why}>
          {card.why}
        </Text>
      ) : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: { width: 138 },
  img: { width: 138, height: 100, backgroundColor: colors.inset },
  quiet: {
    position: "absolute",
    top: 7,
    left: 7,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radii.pill,
    backgroundColor: "rgba(255,255,255,0.94)",
  },
  quietText: { fontSize: 10.5, fontWeight: "800", color: colors.ink },
  heart: {
    position: "absolute",
    top: 7,
    right: 7,
    width: 26,
    height: 26,
    borderRadius: 13,
    backgroundColor: colors.control,
    alignItems: "center",
    justifyContent: "center",
  },
  title: { marginTop: spacing.xs, fontSize: 13.5, fontWeight: "700", color: colors.ink },
  meta: { marginTop: 1, fontSize: 12, color: colors.ter },
  why: { marginTop: 3, fontSize: 11.5, lineHeight: 16, color: colors.sec },
});
