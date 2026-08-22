import { StyleSheet, Text, View } from "react-native";
import { colors } from "@/constants/theme";

export function SectionKicker({ label }: { label: string }) {
  return (
    <View style={styles.kick}>
      <Text style={styles.text}>{label}</Text>
      <View style={styles.rule} />
    </View>
  );
}

const styles = StyleSheet.create({
  kick: { flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 10 },
  text: { fontSize: 11, fontWeight: "800", letterSpacing: 0.2, color: colors.accentText },
  rule: { flex: 1, height: 1, backgroundColor: colors.line },
});
