import { Modal, Pressable, View, Text, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { PrimaryButton } from "@/components/PrimaryButton";
import { accountDeletion } from "@/features/auth/account-deletion";
import { colors, radii, spacing } from "@/constants/theme";

interface Props {
  visible: boolean;
  pending: boolean;
  error: string | null;
  onConfirm: () => void;
  onCancel: () => void;
}

export function DeleteConfirmSheet({ visible, pending, error, onConfirm, onCancel }: Props) {
  const insets = useSafeAreaInsets();
  const dismiss = () => {
    if (!pending) onCancel();
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={dismiss}>
      <Pressable style={styles.scrim} onPress={dismiss} testID="delete-confirm-scrim">
        <Pressable
          style={[styles.sheet, { paddingBottom: insets.bottom + spacing.xxl }]}
          onPress={(event) => event.stopPropagation()}
        >
          <View style={styles.grabber} />
          <Text lineBreakStrategyIOS="hangul-word" style={styles.title}>
            {accountDeletion.confirmTitle}
          </Text>
          <Text lineBreakStrategyIOS="hangul-word" style={styles.body}>
            {accountDeletion.confirmBody}
          </Text>
          {error ? (
            <Text lineBreakStrategyIOS="hangul-word" style={styles.error}>
              {error}
            </Text>
          ) : null}
          <View style={styles.actions}>
            <PrimaryButton
              label={pending ? accountDeletion.pendingLabel : accountDeletion.submitLabel}
              disabled={pending}
              onPress={onConfirm}
              testID="delete-confirm"
            />
            <PrimaryButton
              label={accountDeletion.cancelLabel}
              variant="secondary"
              disabled={pending}
              onPress={onCancel}
              testID="delete-cancel"
            />
          </View>
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
    paddingHorizontal: spacing.lg,
  },
  grabber: {
    alignSelf: "center",
    width: 40,
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.line,
    marginBottom: spacing.lg,
  },
  title: {
    fontSize: 20,
    lineHeight: 28,
    fontWeight: "800",
    letterSpacing: -0.5,
    color: colors.ink,
  },
  body: {
    marginTop: spacing.sm,
    fontSize: 14.5,
    lineHeight: 22,
    letterSpacing: -0.2,
    color: colors.sec,
  },
  error: { marginTop: spacing.sm, fontSize: 13, lineHeight: 19, color: colors.accentText },
  actions: { marginTop: spacing.xl, gap: spacing.sm },
});
