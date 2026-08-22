import { View, Text, Pressable, StyleSheet } from "react-native";
import { Icon } from "@/components/Icon";
import { colors, radii, spacing } from "@/constants/theme";

export const REQUIRED_TAG = "[필수]";
export const OPTIONAL_TAG = "[선택]";
export const SEE_LABEL = "보기";

interface Props {
  required: boolean;
  label: string;
  checked: boolean;
  onToggle?: () => void;
  onSee?: () => void;
  highlighted?: boolean;
  testID?: string;
}

/** 온보딩 목록 · 여행 탭 폴백 · 동의 내역이 같은 행을 쓴다 — 문구가 화면마다 어긋나지 않게. */
export function ConsentRow({
  required,
  label,
  checked,
  onToggle,
  onSee,
  highlighted = false,
  testID,
}: Props) {
  return (
    <Pressable
      accessibilityRole="checkbox"
      accessibilityState={{ checked }}
      accessibilityLabel={`${required ? REQUIRED_TAG : OPTIONAL_TAG} ${label}`}
      onPress={onToggle}
      disabled={onToggle === undefined}
      style={({ pressed }) => [
        styles.row,
        highlighted && styles.highlighted,
        pressed && onToggle !== undefined && styles.pressed,
      ]}
      testID={testID}
    >
      <View style={[styles.check, checked && styles.checkOn]}>
        {checked ? <Icon name="check" size={13} color={colors.onImage} strokeWidth={2.4} /> : null}
      </View>
      <Text style={styles.label}>
        <Text style={required ? styles.required : styles.optional}>
          {required ? REQUIRED_TAG : OPTIONAL_TAG}
        </Text>
        {` ${label}`}
      </Text>
      {onSee ? (
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={`${label} ${SEE_LABEL}`}
          hitSlop={8}
          onPress={onSee}
          style={styles.see}
          testID={testID ? `${testID}-see` : undefined}
        >
          <Text style={styles.seeText}>{SEE_LABEL}</Text>
          <Icon name="chevron-right" size={13} color={colors.ter} strokeWidth={2} />
        </Pressable>
      ) : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 11,
    paddingVertical: 13,
    paddingHorizontal: spacing.md,
  },
  highlighted: { backgroundColor: colors.fill, borderRadius: radii.lg },
  pressed: { opacity: 0.6 },
  check: {
    width: 22,
    height: 22,
    borderRadius: 11,
    marginTop: -1,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1.5,
    borderColor: colors.line,
  },
  checkOn: { backgroundColor: colors.accent, borderColor: colors.accent },
  label: {
    flex: 1,
    fontSize: 13.5,
    lineHeight: 19,
    fontWeight: "500",
    letterSpacing: -0.2,
    color: colors.ink,
  },
  required: { fontWeight: "700", color: colors.sec },
  optional: { fontWeight: "700", color: colors.ter },
  see: { flexDirection: "row", alignItems: "center", gap: 1 },
  seeText: { fontSize: 12.5, lineHeight: 19, fontWeight: "600", color: colors.ter },
});
