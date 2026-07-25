import { useEffect } from "react";
import { View, Text, StyleSheet } from "react-native";
import { colors, radii, spacing } from "@/constants/theme";

const VISIBLE_MS = 2600;

interface Props {
  message: string | null;
  bottom: number;
  onHide: () => void;
}

export function TravelToast({ message, bottom, onHide }: Props) {
  useEffect(() => {
    if (!message) return;
    const timer = setTimeout(onHide, VISIBLE_MS);
    return () => clearTimeout(timer);
  }, [message, onHide]);

  if (!message) return null;

  return (
    <View style={[styles.root, { bottom }]} pointerEvents="none">
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
    padding: 14,
  },
  text: { color: colors.onImage, fontSize: 13.5, lineHeight: 20 },
});
