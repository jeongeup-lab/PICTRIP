import { View, Text, Pressable, StyleSheet } from "react-native";
import { Icon } from "@/components/Icon";
import { colors, spacing } from "@/constants/theme";

interface Props {
  title: string;
  actionLabel?: string;
  onAction?: () => void;
  testID?: string;
}

export function SectionTitle({ title, actionLabel, onAction, testID }: Props) {
  return (
    <View style={styles.head}>
      <Text style={styles.title}>{title}</Text>
      {actionLabel && onAction ? (
        <Pressable
          accessibilityRole="button"
          hitSlop={8}
          onPress={onAction}
          style={styles.action}
          testID={testID}
        >
          <Text style={styles.actionText}>{actionLabel}</Text>
          <Icon name="chevron-right" size={14} color={colors.sec} />
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  head: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: 9,
  },
  title: { fontSize: 13, fontWeight: "800", letterSpacing: -0.1, color: colors.sec },
  actionText: { fontSize: 12.5, fontWeight: "700", color: colors.sec },
  action: { flexDirection: "row", alignItems: "center", gap: 2 },
});
