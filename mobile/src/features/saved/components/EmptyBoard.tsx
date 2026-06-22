import { View, Text, Pressable, StyleSheet } from "react-native";
import { Icon, type IconName } from "@/components/Icon";
import { colors, spacing, radii } from "@/constants/theme";

interface Props {
  text: string;
  actionLabel: string;
  actionIcon: IconName;
  onAction: () => void;
}

export function EmptyBoard({ text, actionLabel, actionIcon, onAction }: Props) {
  return (
    <View style={styles.board}>
      <Text style={styles.text}>{text}</Text>
      <Pressable style={styles.btn} onPress={onAction}>
        <Icon name={actionIcon} size={15} color={colors.ink} />
        <Text style={styles.btnText}>{actionLabel}</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  board: {
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radii.md,
    paddingVertical: 30,
    paddingHorizontal: spacing.md,
    alignItems: "center",
    gap: spacing.md,
    backgroundColor: colors.bg,
  },
  text: { color: colors.ter, fontSize: 14 },
  btn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    height: 38,
    paddingHorizontal: 18,
    borderRadius: radii.pill,
    backgroundColor: colors.fill,
  },
  btnText: { fontSize: 13.5, fontWeight: "700", color: colors.ink },
});
