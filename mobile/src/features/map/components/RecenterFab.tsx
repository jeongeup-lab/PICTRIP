import { Pressable, StyleSheet } from "react-native";
import { Icon } from "@/components/Icon";
import { colors, shadows } from "@/constants/theme";

export function RecenterFab({ onPress }: { onPress: () => void }) {
  return (
    <Pressable style={styles.fab} onPress={onPress} hitSlop={8}>
      <Icon name="recenter" size={22} color={colors.ink} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  fab: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.bg,
    ...shadows.fab,
  },
});
