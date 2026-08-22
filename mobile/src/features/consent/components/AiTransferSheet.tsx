import { Modal, Pressable, View, Text, StyleSheet, Linking } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Icon } from "@/components/Icon";
import { ConsentDetail } from "@/features/consent/components/ConsentDetail";
import { ConsentRow } from "@/features/consent/components/ConsentRow";
import { AI_TRANSFER } from "@/features/consent/lib/ai-transfer";
import { legalUrl } from "@/features/legal/constants";
import { colors, radii, spacing } from "@/constants/theme";

interface Props {
  visible: boolean;
  onAgree: () => void;
  onDecline: () => void;
}

export function AiTransferSheet({ visible, onAgree, onDecline }: Props) {
  const insets = useSafeAreaInsets();

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onDecline}>
      <Pressable style={styles.scrim} onPress={onDecline} testID="ai-transfer-scrim">
        <Pressable
          style={[styles.sheet, { paddingBottom: insets.bottom + spacing.md }]}
          onPress={(event) => event.stopPropagation()}
        >
          <View style={styles.grabber} />

          <Text lineBreakStrategyIOS="hangul-word" style={styles.title}>
            {AI_TRANSFER.sheetTitle}
          </Text>
          <Text lineBreakStrategyIOS="hangul-word" style={styles.body}>
            {AI_TRANSFER.sheetBody}
          </Text>

          <View style={styles.rowSlot}>
            <ConsentRow
              required={false}
              label={AI_TRANSFER.rowLabel}
              checked={false}
              highlighted
              testID="ai-transfer-row"
            />
          </View>
          <ConsentDetail />

          <Text lineBreakStrategyIOS="hangul-word" style={styles.note}>
            {AI_TRANSFER.note}
          </Text>

          <Pressable
            accessibilityRole="link"
            onPress={() => void Linking.openURL(legalUrl("privacy"))}
            style={({ pressed }) => [styles.policy, pressed && styles.pressed]}
            testID="ai-transfer-policy"
          >
            <Text style={styles.policyText}>{AI_TRANSFER.policyLabel}</Text>
            <Icon name="chevron-right" size={14} color={colors.sec} />
          </Pressable>

          <View style={styles.actions}>
            <Pressable
              accessibilityRole="button"
              onPress={onDecline}
              style={({ pressed }) => [styles.button, styles.decline, pressed && styles.pressed]}
              testID="ai-transfer-decline"
            >
              <Text style={styles.declineLabelText}>{AI_TRANSFER.declineLabel}</Text>
            </Pressable>
            <Pressable
              accessibilityRole="button"
              onPress={onAgree}
              style={({ pressed }) => [styles.button, styles.agree, pressed && styles.pressed]}
              testID="ai-transfer-agree"
            >
              <Text style={styles.agreeLabelText}>{AI_TRANSFER.agreeLabel}</Text>
            </Pressable>
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
    marginBottom: spacing.md,
  },
  title: {
    fontSize: 17,
    lineHeight: 24,
    fontWeight: "800",
    letterSpacing: -0.4,
    color: colors.ink,
  },
  body: { marginTop: 6, fontSize: 13, lineHeight: 19, letterSpacing: -0.2, color: colors.sec },
  rowSlot: { marginTop: 12, marginHorizontal: -spacing.md },
  note: { marginTop: 10, fontSize: 12, lineHeight: 18, color: colors.sec },
  policy: {
    marginTop: 9,
    flexDirection: "row",
    alignItems: "center",
    gap: 2,
    paddingVertical: spacing.xs,
  },
  policyText: { fontSize: 12.5, fontWeight: "600", color: colors.sec },
  pressed: { opacity: 0.6 },
  actions: { marginTop: 13, flexDirection: "row", gap: 8 },
  button: { height: 48, borderRadius: radii.md, alignItems: "center", justifyContent: "center" },
  decline: { flex: 34, backgroundColor: colors.fillStrong },
  agree: { flex: 66, backgroundColor: colors.accent },
  declineLabelText: { fontSize: 15, fontWeight: "700", color: colors.ink },
  agreeLabelText: { fontSize: 15, fontWeight: "700", color: colors.onImage },
});
