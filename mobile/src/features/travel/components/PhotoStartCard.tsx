import { Pressable, View, Text, StyleSheet } from "react-native";
import { Icon } from "@/components/Icon";
import { ATTACH_NOTICE } from "@/features/travel/components/AskComposer";
import { colors, radii, spacing } from "@/constants/theme";

export const PHOTO_START_TITLE = "사진으로 찾기";
export const PHOTO_START_BODY = "마음에 든 사진을 올리면 닮은 국내 여행지를 찾아드려요";

interface Props {
  onPress: () => void;
}

export function PhotoStartCard({ onPress }: Props) {
  return (
    <Pressable
      testID="travel-photo-start"
      accessibilityRole="button"
      accessibilityLabel={PHOTO_START_TITLE}
      style={({ pressed }) => [styles.card, pressed && styles.pressed]}
      onPress={onPress}
    >
      <View style={styles.badge}>
        <Icon name="plus" size={18} color={colors.onImage} strokeWidth={2.2} />
      </View>
      <View style={styles.copy}>
        <Text style={styles.title}>{PHOTO_START_TITLE}</Text>
        <Text style={styles.body}>{PHOTO_START_BODY}</Text>
        <Text style={styles.note}>{ATTACH_NOTICE}</Text>
      </View>
      <Icon name="chevron-right" size={16} color={colors.ter} strokeWidth={2} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    marginTop: spacing.lg,
    marginHorizontal: spacing.lg,
    padding: spacing.md + 2,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.inset,
  },
  pressed: { backgroundColor: colors.fill },
  badge: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.ink,
  },
  copy: { flex: 1 },
  title: { fontSize: 15, fontWeight: "800", letterSpacing: -0.3, color: colors.ink },
  body: { marginTop: 3, fontSize: 12.5, lineHeight: 18, color: colors.sec },
  note: { marginTop: 4, fontSize: 11.5, color: colors.ter },
});
