import { useEffect } from "react";
import { Modal, Pressable, View, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router } from "expo-router";
import { LoginCard } from "@/features/auth/components/LoginCard";
import { useAuthPromptStore } from "@/features/auth/stores/auth-prompt-store";
import { useAuthStore } from "@/features/auth/stores/auth-store";
import { colors, spacing, radii } from "@/constants/theme";

/** Root-mounted bottom sheet for the login nudge (save 등 inline 승격).
 * Driven by the auth-prompt store; resolves the pending action on success. */
export function AuthPromptSheet() {
  const insets = useSafeAreaInsets();
  const visible = useAuthPromptStore((s) => s.visible);
  const resolve = useAuthPromptStore((s) => s.resolve);
  const succeed = useAuthPromptStore((s) => s.succeed);
  const hide = useAuthPromptStore((s) => s.hide);
  const dismiss = useAuthPromptStore((s) => s.dismiss);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  // Resume a pending action (e.g. save) once the user becomes authenticated by
  // ANY path — crucially the email screen, which logs in on a separate route and
  // can't call succeed() directly. OAuth flows through here harmlessly: succeed()
  // clears `resolve`, so this no-ops after the direct onSuccess call.
  useEffect(() => {
    if (isAuthenticated && resolve) succeed();
  }, [isAuthenticated, resolve, succeed]);

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={dismiss}>
      <Pressable style={styles.scrim} onPress={dismiss}>
        <Pressable
          style={[styles.sheet, { paddingBottom: insets.bottom + spacing.lg }]}
          onPress={(e) => e.stopPropagation()}
        >
          <View style={styles.grabber} />
          <LoginCard
            variant="sheet"
            onSuccess={succeed}
            onCancel={dismiss}
            onEmailPress={() => {
              // Close the native Modal first (keeping the pending action armed),
              // THEN route to the email screen — pushing under an open Modal
              // renders the screen behind the sheet. The isAuthenticated effect
              // above resumes the pending action once email login succeeds.
              hide();
              router.push("/auth/email");
            }}
          />
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
