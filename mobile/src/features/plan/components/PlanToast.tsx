import { useEffect } from "react";
import { View, Text, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { colors, radii, spacing } from "@/constants/theme";

const VISIBLE_MS = 2800;

interface Props {
  message: string | null;
  onHide: () => void;
}

export function PlanToast({ message, onHide }: Props) {
  const insets = useSafeAreaInsets();

  useEffect(() => {
    if (!message) return;
    const timer = setTimeout(onHide, VISIBLE_MS);
    return () => clearTimeout(timer);
  }, [message, onHide]);

  if (!message) return null;

  return (
    <View style={[styles.root, { bottom: insets.bottom + spacing.xl }]} pointerEvents="none">
      <Text style={styles.text}>{message}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    position: "absolute",
    left: spacing.lg,
    right: spacing.lg,
    backgroundColor: colors.ink,
    borderRadius: radii.lg,
    paddingVertical: 14,
    paddingHorizontal: spacing.md,
  },
  text: { color: colors.onImage, fontSize: 13.5, lineHeight: 20 },
});
