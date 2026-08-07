import { View, Text, Pressable, StyleSheet } from "react-native";
import { Icon } from "@/components/Icon";
import { colors, radii, spacing } from "@/constants/theme";

export function GuestHero({ onPress }: { onPress: () => void }) {
  return (
    <Pressable accessibilityRole="button" style={styles.hero} onPress={onPress} testID="guest-hero">
      <View style={styles.avatar}>
        <Icon name="person" size={24} color={colors.sec} />
      </View>
      <View style={styles.text}>
        <Text style={styles.title}>로그인하기</Text>
        <Text style={styles.sub}>스크랩과 기록을 안전하게 보관해요</Text>
      </View>
      <Icon name="chevron-right" size={18} color={colors.ter} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  hero: {
    flexDirection: "row",
    alignItems: "center",
    gap: 13,
    marginHorizontal: spacing.md,
    marginTop: spacing.sm,
    paddingVertical: 20,
    paddingHorizontal: spacing.md + 2,
    borderRadius: radii.lg + 8,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.raise,
  },
  avatar: {
    width: 50,
    height: 50,
    borderRadius: 25,
    backgroundColor: colors.fill,
    borderWidth: 1,
    borderColor: colors.glassBorder,
    alignItems: "center",
    justifyContent: "center",
  },
  text: { flex: 1, minWidth: 0 },
  title: { fontSize: 18, fontWeight: "800", letterSpacing: -0.4, color: colors.ink },
  sub: { marginTop: 4, fontSize: 12.5, color: colors.sec },
});
