import { View, Text, Pressable, StyleSheet } from "react-native";
import { router, type Href } from "expo-router";
import { Icon } from "@/components/Icon";
import { colors, spacing } from "@/constants/theme";

interface ScreenHeaderProps {
  readonly title: string;
  readonly fallback: Href;
  readonly disabled?: boolean;
}

export function ScreenHeader({ title, fallback, disabled = false }: ScreenHeaderProps) {
  const onBack = () => {
    if (disabled) return;
    if (router.canGoBack()) {
      router.back();
      return;
    }
    router.replace(fallback);
  };

  return (
    <View style={styles.root}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="뒤로"
        accessibilityState={{ disabled }}
        disabled={disabled}
        hitSlop={8}
        onPress={onBack}
        style={({ pressed }) => [
          styles.back,
          disabled && styles.disabled,
          pressed && styles.pressed,
        ]}
        testID="screen-header-back"
      >
        <Icon name="chevron-left" size={23} />
      </Pressable>
      <Text pointerEvents="none" style={styles.title} numberOfLines={1}>
        {title}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    height: 50,
    flexDirection: "row",
    alignItems: "center",
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  back: {
    width: 48,
    height: 48,
    alignItems: "center",
    justifyContent: "center",
    marginLeft: spacing.xs,
    borderRadius: 24,
  },
  pressed: { backgroundColor: colors.fill },
  disabled: { opacity: 0.45 },
  title: {
    position: "absolute",
    left: 56,
    right: 56,
    textAlign: "center",
    fontSize: 17,
    fontWeight: "700",
    color: colors.ink,
  },
});
