import { Pressable, Text, StyleSheet } from "react-native";
import { colors, radii } from "@/constants/theme";

interface PrimaryButtonProps {
  label: string;
  onPress: () => void;
  variant?: "primary" | "secondary";
  disabled?: boolean;
}

export function PrimaryButton({
  label,
  onPress,
  variant = "primary",
  disabled,
}: PrimaryButtonProps) {
  const isPrimary = variant === "primary";
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      style={[
        styles.base,
        { backgroundColor: isPrimary ? colors.ink : colors.inset, opacity: disabled ? 0.4 : 1 },
      ]}
    >
      <Text style={[styles.label, { color: isPrimary ? colors.onImage : colors.ink }]}>
        {label}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    height: 54,
    borderRadius: radii.md,
    alignItems: "center",
    justifyContent: "center",
  },
  label: { fontSize: 16, fontWeight: "700" },
});
