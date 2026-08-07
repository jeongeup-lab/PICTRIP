import { useEffect } from "react";
import { Pressable, View, Text, StyleSheet } from "react-native";
import { colors, radii, spacing } from "@/constants/theme";

export const TOAST_VISIBLE_MS = 2600;

/** An undoable toast has to outlive the reading of it, or the offer is a lie. */
export const TOAST_UNDO_MS = 5000;

export interface ToastAction {
  label: string;
  onPress: () => void;
}

interface Props {
  message: string | null;
  bottom: number;
  onHide: () => void;
  action?: ToastAction | null;
  durationMs?: number;
  testID?: string;
}

export function Toast({
  message,
  bottom,
  onHide,
  action = null,
  durationMs = TOAST_VISIBLE_MS,
  testID,
}: Props) {
  useEffect(() => {
    if (!message) return;
    const timer = setTimeout(onHide, durationMs);
    return () => clearTimeout(timer);
  }, [message, onHide, durationMs]);

  if (!message) return null;

  return (
    <View style={[styles.root, { bottom }]} pointerEvents="box-none" testID={testID}>
      <Text style={styles.text} numberOfLines={2}>
        {message}
      </Text>
      {action ? (
        <Pressable
          accessibilityRole="button"
          hitSlop={8}
          onPress={action.onPress}
          testID={testID ? `${testID}-action` : undefined}
        >
          <Text style={styles.action}>{action.label}</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    position: "absolute",
    left: spacing.lg,
    right: spacing.lg,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: colors.fillStrong,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radii.lg,
    padding: 14,
  },
  text: { flex: 1, color: colors.onImage, fontSize: 13.5, lineHeight: 20 },
  action: { color: colors.info, fontSize: 13, fontWeight: "700" },
});
