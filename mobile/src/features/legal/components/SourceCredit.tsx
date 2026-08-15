import { Pressable, Text, StyleSheet } from "react-native";
import { router } from "expo-router";
import { Icon } from "@/components/Icon";
import { KTO_CREDIT } from "@/features/legal/constants";
import { colors, spacing } from "@/constants/theme";

export function SourceCredit() {
  return (
    <Pressable
      accessibilityRole="link"
      accessibilityLabel={`${KTO_CREDIT}. 데이터 출처와 이용 조건 보기`}
      onPress={() => router.push("/legal/data-sources")}
      style={({ pressed }) => [styles.row, pressed && styles.pressed]}
      testID="source-credit"
    >
      <Text style={styles.text}>{KTO_CREDIT}</Text>
      <Icon name="chevron-right" size={13} color={colors.ter} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 2,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: spacing.xs,
  },
  text: { fontSize: 12, lineHeight: 18, color: colors.ter },
  pressed: { opacity: 0.6 },
});
