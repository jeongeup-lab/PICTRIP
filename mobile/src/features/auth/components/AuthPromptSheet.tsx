import { Modal, Pressable, View, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { LoginCard } from "@/features/auth/components/LoginCard";
import { useAuthPromptStore } from "@/features/auth/stores/auth-prompt-store";
import { colors, spacing, radii } from "@/constants/theme";

/** Root-mounted bottom sheet for the login nudge (save 등 inline 승격).
 * Driven by the auth-prompt store; resolves the pending action on success. */
export function AuthPromptSheet() {
  const insets = useSafeAreaInsets();
  const visible = useAuthPromptStore((s) => s.visible);
  const succeed = useAuthPromptStore((s) => s.succeed);
  const dismiss = useAuthPromptStore((s) => s.dismiss);

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={dismiss}>
      <Pressable style={styles.scrim} onPress={dismiss}>
        <Pressable
          style={[styles.sheet, { paddingBottom: insets.bottom + spacing.lg }]}
          onPress={(e) => e.stopPropagation()}
        >
          <View style={styles.grabber} />
          <LoginCard variant="sheet" onSuccess={succeed} onCancel={dismiss} />
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  scrim: { flex: 1, justifyContent: "flex-end", backgroundColor: colors.scrim },
  sheet: {
    backgroundColor: colors.bg,
    borderTopLeftRadius: radii.xl,
    borderTopRightRadius: radii.xl,
    paddingTop: spacing.md,
    paddingHorizontal: spacing.xs,
  },
  grabber: {
    alignSelf: "center",
    width: 40,
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.line,
    marginBottom: spacing.md,
  },
});
