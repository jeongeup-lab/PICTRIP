import { Pressable, View, Text, StyleSheet } from "react-native";
import { Icon } from "@/components/Icon";
import { colors, spacing } from "@/constants/theme";

export function GuestLoginRow({ onPress }: { onPress: () => void }) {
  return (
    <Pressable style={styles.row} onPress={onPress}>
      <View style={styles.avatar}>
        <Icon name="person" size={26} color={colors.ink} />
      </View>
      <View style={styles.tx}>
        <Text style={styles.title}>로그인하기</Text>
        <Text style={styles.sub}>나만의 여행지를 스크랩해 보세요</Text>
      </View>
      <Icon name="chevron-right" size={20} color={colors.ter} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
    paddingVertical: 22,
    paddingHorizontal: spacing.lg,
    backgroundColor: colors.bg,
  },
  avatar: {
    width: 54,
    height: 54,
    borderRadius: 27,
    backgroundColor: colors.fill,
    alignItems: "center",
    justifyContent: "center",
  },
  tx: { flex: 1 },
  title: { fontSize: 18, fontWeight: "700", letterSpacing: -0.18, color: colors.ink },
  sub: { color: colors.sec, fontSize: 13, marginTop: 3 },
});
