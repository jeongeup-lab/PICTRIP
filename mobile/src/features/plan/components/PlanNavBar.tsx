import { Pressable, View, Text, StyleSheet } from "react-native";
import { Icon } from "@/components/Icon";
import { colors } from "@/constants/theme";

interface Props {
  title: string;
  onBack: () => void;
}

export function PlanNavBar({ title, onBack }: Props) {
  return (
    <View style={styles.nav}>
      <Pressable style={styles.button} onPress={onBack} hitSlop={8} testID="plan-back">
        <Icon name="chevron-left" size={23} />
      </Pressable>
      <Text style={styles.title} numberOfLines={1}>
        {title}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  nav: {
    height: 50,
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.bg,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  button: { width: 44, height: 44, alignItems: "center", justifyContent: "center", zIndex: 1 },
  title: {
    position: "absolute",
    left: 56,
    right: 56,
    textAlign: "center",
    fontSize: 17,
    fontWeight: "700",
    letterSpacing: -0.35,
    color: colors.ink,
  },
});
