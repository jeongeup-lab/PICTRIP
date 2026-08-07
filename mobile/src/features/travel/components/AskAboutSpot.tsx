import { Pressable, View, Text, StyleSheet } from "react-native";
import { Icon } from "@/components/Icon";
import { colors, radii, spacing } from "@/constants/theme";

export const ASK_ABOUT_SUFFIX = "에 대해 물어보기";

interface Props {
  title: string;
  onPress: () => void;
}

export function AskAboutSpot({ title, onPress }: Props) {
  return (
    <Pressable
      testID="spot-ask-about"
      accessibilityRole="button"
      accessibilityLabel={`${title}${ASK_ABOUT_SUFFIX}`}
      style={({ pressed }) => [styles.field, pressed && styles.pressed]}
      onPress={onPress}
    >
      <View style={styles.token}>
        <Text style={styles.tokenText} numberOfLines={1}>
          {title}
        </Text>
      </View>
      <Text style={styles.suffix} numberOfLines={1}>
        {ASK_ABOUT_SUFFIX}
      </Text>
      <View style={styles.go}>
        <Icon name="arrow-up" size={17} color={colors.onImage} strokeWidth={2.3} />
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  field: {
    flexDirection: "row",
    alignItems: "center",
    gap: 9,
    marginTop: 22,
    marginHorizontal: spacing.lg,
    height: 46,
    paddingLeft: 8,
    paddingRight: 6,
    borderRadius: 13,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.inset,
  },
  pressed: { opacity: 0.75 },
  token: {
    maxWidth: "56%",
    paddingVertical: 4,
    paddingHorizontal: 8,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: "rgba(255,59,83,0.4)",
    backgroundColor: colors.accentFill,
  },
  tokenText: { fontSize: 12, fontWeight: "700", color: colors.accentText },
  suffix: { flex: 1, fontSize: 14, color: colors.sec },
  go: {
    width: 32,
    height: 32,
    borderRadius: radii.md,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.accent,
  },
});
