import { Pressable, View, Text, StyleSheet } from "react-native";
import { Icon, type IconName } from "@/components/Icon";
import { colors, radii, shadows, spacing } from "@/constants/theme";

interface Props {
  icon: IconName;
  title: string;
  caption: string;
  accent?: boolean;
  testID?: string;
  onPress: () => void;
}

export function StartCard({ icon, title, caption, accent, testID, onPress }: Props) {
  return (
    <Pressable
      testID={testID}
      style={({ pressed }) => [styles.card, pressed && styles.pressed]}
      onPress={onPress}
    >
      <View style={styles.glyph}>
        <Icon name={icon} size={22} color={accent ? colors.accentText : colors.ink} />
      </View>
      <View style={styles.body}>
        <Text style={styles.title}>{title}</Text>
        <Text style={styles.caption}>{caption}</Text>
      </View>
      <Icon name="chevron-right" size={20} color={colors.ter} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    backgroundColor: colors.bg,
    borderRadius: radii.lg,
    paddingVertical: 17,
    paddingHorizontal: spacing.md,
    marginTop: 12,
    ...shadows.card,
  },
  pressed: { opacity: 0.9 },
  glyph: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.inset,
    alignItems: "center",
    justifyContent: "center",
  },
  body: { flex: 1 },
  title: { fontSize: 16, fontWeight: "700", letterSpacing: -0.3, color: colors.ink },
  caption: { marginTop: 3, fontSize: 13, color: colors.sec },
});
