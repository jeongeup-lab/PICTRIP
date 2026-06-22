import { type ReactNode } from "react";
import { View, Text, Pressable, StyleSheet } from "react-native";
import { Icon } from "@/components/Icon";
import { colors } from "@/constants/theme";

interface AppBarProps {
  title?: string;
  onBack?: () => void;
  right?: ReactNode;
}

export function AppBar({ title, onBack, right }: AppBarProps) {
  return (
    <View style={styles.bar}>
      <View style={styles.side}>
        {onBack && (
          <Pressable onPress={onBack} hitSlop={8} style={styles.circle}>
            <Icon name="chevron-left" size={22} />
          </Pressable>
        )}
      </View>
      <Text numberOfLines={1} style={styles.title}>
        {title}
      </Text>
      <View style={[styles.side, { alignItems: "flex-end" }]}>{right}</View>
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    height: 50,
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 12,
  },
  side: { width: 44, justifyContent: "center" },
  circle: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.inset,
  },
  title: { flex: 1, textAlign: "center", fontSize: 16, fontWeight: "700", color: colors.ink },
});
