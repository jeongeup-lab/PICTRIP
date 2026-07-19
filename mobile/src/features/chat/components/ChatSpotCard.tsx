import { Pressable, View, Text, StyleSheet } from "react-native";
import { RemoteImage } from "@/components/RemoteImage";
import { colors, radii, spacing } from "@/constants/theme";
import type { ChatCard } from "@/features/chat/types";

interface Props {
  card: ChatCard;
  onPress: () => void;
  onPressIn?: () => void;
}

export function ChatSpotCard({ card, onPress, onPressIn }: Props) {
  const meta = [card.regionLabel, card.category].filter(Boolean).join(" · ");
  return (
    <Pressable style={styles.card} onPress={onPress} onPressIn={onPressIn}>
      <View>
        <RemoteImage uri={card.firstImageUrl} radius={radii.md} style={styles.img} />
        {card.quiet ? (
          <View style={styles.quiet}>
            <Text style={styles.quietText}>지금 한산</Text>
          </View>
        ) : null}
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
  title: { marginTop: spacing.xs, fontSize: 13.5, fontWeight: "700", color: colors.ink },
  meta: { marginTop: 1, fontSize: 12, color: colors.ter },
  why: { marginTop: 3, fontSize: 11.5, lineHeight: 16, color: colors.sec },
});
