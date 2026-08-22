import { View, Text, StyleSheet } from "react-native";
import { AI_TRANSFER } from "@/features/consent/lib/ai-transfer";
import { colors, radii } from "@/constants/theme";

/** 법 제28조의8 제2항 각 호. 동의 버튼과 같은 화면에 있어야 하므로 접거나 링크 뒤로 보내지 않는다. */
export function ConsentDetail({ testID }: { testID?: string }) {
  return (
    <View style={styles.table} testID={testID}>
      {AI_TRANSFER.items.map((item, index) => (
        <View
          key={item.key}
          style={[styles.row, index > 0 && styles.divided]}
          testID={`ai-transfer-${item.key}`}
        >
          <Text style={styles.key}>{item.label}</Text>
          <Text lineBreakStrategyIOS="hangul-word" style={styles.value}>
            {item.value}
          </Text>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  table: {
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radii.lg,
    overflow: "hidden",
  },
  row: { flexDirection: "row", gap: 10, paddingVertical: 9, paddingHorizontal: 11 },
  divided: { borderTopWidth: 1, borderTopColor: colors.line },
  key: { width: 62, fontSize: 11.5, lineHeight: 17, fontWeight: "700", color: colors.ter },
  value: {
    flex: 1,
    minWidth: 0,
    fontSize: 12.5,
    lineHeight: 17,
    fontWeight: "500",
    letterSpacing: -0.2,
    color: colors.ink,
  },
});
