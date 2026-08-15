import { Modal, Pressable, View, Text, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router } from "expo-router";
import { Icon } from "@/components/Icon";
import { PrimaryButton } from "@/components/PrimaryButton";
import { AI_CONSENT } from "@/features/travel/lib/ai-consent";
import { colors, radii, spacing } from "@/constants/theme";

interface Props {
  visible: boolean;
  onAgree: () => void;
  onDecline: () => void;
}

export function AiConsentSheet({ visible, onAgree, onDecline }: Props) {
  const insets = useSafeAreaInsets();

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onDecline}>
      <Pressable style={styles.scrim} onPress={onDecline} testID="ai-consent-scrim">
        <Pressable
          style={[styles.sheet, { paddingBottom: insets.bottom + spacing.xxl }]}
          onPress={(event) => event.stopPropagation()}
        >
          <View style={styles.grabber} />
          <Text lineBreakStrategyIOS="hangul-word" style={styles.title}>
            {AI_CONSENT.title}
          </Text>
          <Text lineBreakStrategyIOS="hangul-word" style={styles.body}>
            {AI_CONSENT.body}
          </Text>
          <View style={styles.notes}>
            <View style={styles.note}>
              <Icon name="shield-check" size={16} color={colors.sec} />
              <Text lineBreakStrategyIOS="hangul-word" style={styles.noteText}>
                {AI_CONSENT.scope}
              </Text>
            </View>
            <View style={styles.note}>
              <Icon name="info" size={16} color={colors.sec} />
              <Text lineBreakStrategyIOS="hangul-word" style={styles.noteText}>
                {AI_CONSENT.fallback}
              </Text>
            </View>
          </View>
          <Pressable
            accessibilityRole="link"
            onPress={() => router.push("/legal/privacy")}
            style={({ pressed }) => [styles.policy, pressed && styles.pressed]}
            testID="ai-consent-policy"
          >
            <Text style={styles.policyText}>{AI_CONSENT.policyLabel}</Text>
            <Icon name="chevron-right" size={15} color={colors.sec} />
          </Pressable>
          <View style={styles.actions}>
            <PrimaryButton
              label={AI_CONSENT.agreeLabel}
              onPress={onAgree}
              testID="ai-consent-agree"
            />
            <PrimaryButton
              label={AI_CONSENT.declineLabel}
              variant="secondary"
              onPress={onDecline}
              testID="ai-consent-decline"
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
  notes: { marginTop: spacing.md, gap: spacing.sm },
  note: { flexDirection: "row", alignItems: "flex-start", gap: 9 },
  noteText: { flex: 1, fontSize: 13.5, lineHeight: 20, color: colors.sec },
  policy: {
    marginTop: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    gap: 2,
    paddingVertical: spacing.xs,
  },
  policyText: { fontSize: 13.5, fontWeight: "600", color: colors.sec },
  pressed: { opacity: 0.6 },
  actions: { marginTop: spacing.lg, gap: spacing.sm },
});
