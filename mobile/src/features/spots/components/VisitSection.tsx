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
          <Icon name="share" size={22} color={colors.sec} />
        </Pressable>
        <Pressable style={styles.card} onPress={onScrap}>
          <Text style={styles.cardText}>스크랩</Text>
          <Icon name="bookmark" size={22} color={colors.sec} />
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  visit: {
    backgroundColor: colors.inset,
    marginTop: 30,
    paddingVertical: 26,
    paddingHorizontal: 20,
  },
  h3: { fontSize: 19, fontWeight: "800", letterSpacing: -0.38, color: colors.ink },
  cards: { flexDirection: "row", gap: 12, marginTop: 16 },
  card: {
    flex: 1,
    height: 60,
    backgroundColor: colors.bg,
    borderRadius: 12,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 18,
  },
  cardText: { fontSize: 15, fontWeight: "700", color: colors.ink },
});
