import { View, Text, Pressable, StyleSheet } from "react-native";
import { Icon } from "@/components/Icon";
import { colors } from "@/constants/theme";

interface VisitSectionProps {
  title: string;
  onShare: () => void;
  onScrap: () => void;
}

/** 방문 예정 inset block: 공유 / 스크랩 cards. */
export function VisitSection({ title, onShare, onScrap }: VisitSectionProps) {
  return (
    <View style={styles.visit}>
      <Text style={styles.h3}>{title}에 방문 예정이신가요?</Text>
      <View style={styles.cards}>
        <Pressable style={styles.card} onPress={onShare}>
          <Text style={styles.cardText}>공유</Text>
          <Icon name="share" size={19} color={colors.sec} />
        </Pressable>
        <Pressable style={styles.card} onPress={onScrap}>
          <Text style={styles.cardText}>스크랩</Text>
          <Icon name="bookmark" size={19} color={colors.accentText} />
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
  cardText: { fontSize: 14, fontWeight: "700", color: colors.ink },
});
