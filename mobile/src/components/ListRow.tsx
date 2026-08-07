import type { ReactNode } from "react";
import { View, Text, Pressable, StyleSheet } from "react-native";
import { Icon, type IconName } from "@/components/Icon";
import { colors, spacing } from "@/constants/theme";

export type ListRowTone = "muted" | "on" | "off" | "danger";

interface Props {
  icon?: IconName;
  title: string;
  sub?: string | null;
  value?: string | null;
  tone?: ListRowTone;
  danger?: boolean;
  right?: ReactNode;
  chevron?: boolean;
  onPress?: () => void;
  testID?: string;
}

const TONE_STYLE = {
  muted: undefined,
  on: { color: colors.positive },
  off: { color: colors.ter },
  danger: { color: colors.accentText },
} as const;

export function ListRow({
  icon,
  title,
  sub,
  value,
  tone = "muted",
  danger = false,
  right,
  chevron = false,
  onPress,
  testID,
}: Props) {
  const body = (
    <View style={styles.row}>
      {icon ? (
        <View style={styles.icon}>
          <Icon name={icon} size={17} color={danger ? colors.accent : colors.sec} />
        </View>
      ) : null}
      <View style={styles.main}>
        <Text style={[styles.title, danger && styles.titleDanger]} numberOfLines={1}>
          {title}
        </Text>
        {sub ? (
          <Text style={styles.sub} numberOfLines={2}>
            {sub}
          </Text>
        ) : null}
      </View>
      {value ? <Text style={[styles.value, TONE_STYLE[tone]]}>{value}</Text> : null}
      {right}
      {chevron ? <Icon name="chevron-right" size={17} color={colors.ter} /> : null}
    </View>
  );

  if (!onPress) return <View testID={testID}>{body}</View>;
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      testID={testID}
      style={({ pressed }) => (pressed ? styles.pressed : undefined)}
    >
      {body}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 11,
    minHeight: 52,
    paddingVertical: 12,
    paddingHorizontal: spacing.md,
  },
  pressed: { backgroundColor: colors.fill },
  icon: { width: 20, alignItems: "center" },
  main: { flex: 1, gap: 3 },
  title: { fontSize: 14.5, fontWeight: "600", color: colors.ink },
  titleDanger: { color: colors.accentText },
  sub: { fontSize: 12, lineHeight: 17, color: colors.ter },
  value: { fontSize: 13, fontWeight: "600", color: colors.sec, maxWidth: 170 },
});
