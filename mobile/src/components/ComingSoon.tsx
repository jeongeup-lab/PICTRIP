import { View, Text, StyleSheet } from "react-native";
import { colors } from "@/constants/theme";

export function ComingSoon({ label }: { label: string }) {
  return (
    <View style={styles.wrap}>
      <Text style={styles.text}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.bg },
  text: { fontSize: 15, color: colors.ter },
});
