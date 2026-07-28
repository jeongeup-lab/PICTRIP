import { Pressable, View, Text, StyleSheet, type StyleProp, type ViewStyle } from "react-native";
import { Icon } from "@/components/Icon";
import { colors, spacing } from "@/constants/theme";

export const PHOTO_START_TITLE = "사진으로 찾기";
export const PHOTO_START_BODY = "닮은 곳을 찾아드려요";

interface Props {
  onPress: () => void;
  style?: StyleProp<ViewStyle>;
}

export function PhotoStartCard({ onPress, style }: Props) {
  return (
    <Pressable
      testID="travel-photo-start"
      accessibilityRole="button"
      accessibilityLabel={PHOTO_START_TITLE}
      style={({ pressed }) => [styles.pin, style, pressed && styles.pressed]}
      onPress={onPress}
    >
      <View style={styles.badge}>
        <Icon name="plus" size={18} color={colors.onImage} strokeWidth={2.2} />
      </View>
      <Text style={styles.title}>{PHOTO_START_TITLE}</Text>
      <Text style={styles.body}>{PHOTO_START_BODY}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  pin: {
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.md,
    borderRadius: 16,
    borderWidth: 1.5,
    borderStyle: "dashed",
    borderColor: "rgba(112,115,124,0.35)",
    backgroundColor: colors.inset,
  },
  pressed: { backgroundColor: colors.fill },
  badge: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.ink,
  },
  title: { marginTop: 10, fontSize: 14, fontWeight: "800", letterSpacing: -0.3, color: colors.ink },
  body: { marginTop: 4, fontSize: 11.5, lineHeight: 16, textAlign: "center", color: colors.sec },
});
