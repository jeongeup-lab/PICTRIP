import { View, Text, Pressable, StyleSheet } from "react-native";
import { Icon } from "@/components/Icon";
import { colors } from "@/constants/theme";

interface VisitSectionProps {
  title: string;
  saved: boolean;
  onShare: () => void;
  onScrap: () => void;
}

export function VisitSection({ title, saved, onShare, onScrap }: VisitSectionProps) {
  return (
    <View style={styles.visit}>
      <Text style={styles.h3}>{title}에 방문 예정이신가요?</Text>
      <View style={styles.cards}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="공유"
          style={({ pressed }) => [styles.card, pressed && styles.pressed]}
          onPress={onShare}
          testID="visit-share"
        >
          <Text style={styles.cardText}>공유</Text>
          <Icon name="share" size={19} color={colors.sec} />
        </Pressable>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={saved ? "스크랩 해제" : "스크랩"}
          accessibilityState={{ selected: saved }}
          style={({ pressed }) => [styles.card, saved && styles.cardOn, pressed && styles.pressed]}
          onPress={onScrap}
          testID="visit-scrap"
        >
          <Text style={[styles.cardText, saved && styles.cardTextOn]}>
            {saved ? "스크랩됨" : "스크랩"}
          </Text>
          <Icon
            name={saved ? "bookmark-fill" : "bookmark"}
            size={19}
            color={saved ? colors.accent : colors.sec}
          />
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  visit: {
    backgroundColor: colors.inset,
    marginTop: 22,
    paddingVertical: 24,
    paddingHorizontal: 20,
    borderTopWidth: 1,
    borderTopColor: colors.fill,
  },
  h3: { fontSize: 17, fontWeight: "800", letterSpacing: -0.35, color: colors.ink },
  cards: { flexDirection: "row", gap: 10, marginTop: 14 },
  card: {
    flex: 1,
    height: 54,
    backgroundColor: colors.bg,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.fillStrong,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
  },
  cardOn: { borderColor: colors.accent, backgroundColor: colors.accentFill },
  cardText: { fontSize: 14, fontWeight: "700", color: colors.ink },
  cardTextOn: { color: colors.accentText },
  pressed: { opacity: 0.72 },
});
