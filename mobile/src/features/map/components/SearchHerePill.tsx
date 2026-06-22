import { Pressable, Text, StyleSheet } from "react-native";
import { Icon } from "@/components/Icon";
import { colors, radii, shadows } from "@/constants/theme";

export function SearchHerePill({ onPress }: { onPress: () => void }) {
  return (
    <Pressable style={styles.pill} onPress={onPress}>
      <Icon name="search" size={15} color={colors.ink} />
      <Text style={styles.text}>이 지역에서 검색</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  pill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    alignSelf: "center",
    height: 38,
    paddingHorizontal: 16,
    borderRadius: radii.pill,
    backgroundColor: colors.bg,
    ...shadows.fab,
  },
  text: { fontSize: 13.5, fontWeight: "700", color: colors.ink },
});
