import { View, Text, StyleSheet } from "react-native";
import { Icon, type IconName } from "@/components/Icon";
import { colors } from "@/constants/theme";

interface Props {
  icon: IconName;
  strong: string;
  suffix?: string;
  prefix?: string;
}

export function PlanStat({ icon, strong, suffix, prefix }: Props) {
  return (
    <View style={styles.stat}>
      <Icon name={icon} size={13} color={colors.ter} />
      {prefix ? <Text style={styles.text}>{prefix}</Text> : null}
      <Text style={styles.strong}>{strong}</Text>
      {suffix ? <Text style={styles.text}>{suffix}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  stat: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    height: 28,
    paddingHorizontal: 11,
    borderRadius: 14,
    backgroundColor: colors.fill,
  },
  text: { fontSize: 12, fontWeight: "600", color: colors.sec },
  strong: { fontSize: 12, fontWeight: "700", color: colors.ink },
});
