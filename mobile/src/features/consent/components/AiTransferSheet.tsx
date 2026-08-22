import { Modal, Pressable, ScrollView, View, Text, StyleSheet, Linking } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Icon } from "@/components/Icon";
import { PrimaryButton } from "@/components/PrimaryButton";
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
          style={[styles.sheet, { paddingBottom: insets.bottom + spacing.xl }]}
          onPress={(event) => event.stopPropagation()}
        >
          <View style={styles.grabber} />

          <Text lineBreakStrategyIOS="hangul-word" style={styles.title}>
            {AI_TRANSFER.sheetTitle}
          </Text>
          <Text lineBreakStrategyIOS="hangul-word" style={styles.body}>
            {AI_TRANSFER.sheetBody}
          </Text>

          <ScrollView style={styles.list} showsVerticalScrollIndicator={false}>
            {AI_TRANSFER.items.map((item) => (
              <View key={item.key} style={styles.item} testID={`ai-transfer-${item.key}`}>
                <View style={styles.itemIcon}>
                  <Icon name={item.icon} size={15} color={colors.sec} strokeWidth={1.9} />
                </View>
                <View style={styles.itemCopy}>
                  <Text style={styles.itemLabel}>{item.label}</Text>
                  <Text lineBreakStrategyIOS="hangul-word" style={styles.itemValue}>
                    {item.value}
                  </Text>
                </View>
              </View>
            ))}

            <View style={styles.notes}>
              <View style={styles.note}>
                <Icon name="shield-check" size={15} color={colors.sec} strokeWidth={1.9} />
                <Text lineBreakStrategyIOS="hangul-word" style={styles.noteText}>
                  {AI_TRANSFER.scope}
                </Text>
              </View>
              <View style={styles.note}>
                <Icon name="info" size={15} color={colors.sec} strokeWidth={1.9} />
                <Text lineBreakStrategyIOS="hangul-word" style={styles.noteText}>
                  {AI_TRANSFER.refuse}
                </Text>
              </View>
            </View>
          </ScrollView>

          <Pressable
            accessibilityRole="link"
            onPress={() => void Linking.openURL(legalUrl("privacy"))}
            style={({ pressed }) => [styles.policy, pressed && styles.pressed]}
            testID="ai-transfer-policy"
          >
            <Text style={styles.policyText}>{AI_TRANSFER.policyLabel}</Text>
            <Icon name="chevron-right" size={15} color={colors.sec} />
          </Pressable>

          <View style={styles.actions}>
            <PrimaryButton
              label={AI_TRANSFER.agreeLabel}
              onPress={onAgree}
              testID="ai-transfer-agree"
            />
            <PrimaryButton
              label={AI_TRANSFER.declineLabel}
              variant="secondary"
              onPress={onDecline}
              testID="ai-transfer-decline"
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
    maxHeight: "88%",
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
  list: { marginTop: spacing.md },
  item: { flexDirection: "row", alignItems: "flex-start", gap: 10, marginBottom: spacing.md },
  itemIcon: { width: 22, alignItems: "center", paddingTop: 2 },
  itemCopy: { flex: 1, minWidth: 0 },
  itemLabel: { fontSize: 12, fontWeight: "700", letterSpacing: -0.2, color: colors.ter },
  itemValue: {
    marginTop: 3,
    fontSize: 13.5,
    lineHeight: 20,
    letterSpacing: -0.2,
    color: colors.ink,
  },
  notes: {
    marginTop: spacing.xs,
    paddingTop: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.line,
    gap: spacing.sm,
  },
  note: { flexDirection: "row", alignItems: "flex-start", gap: 9 },
  noteText: { flex: 1, fontSize: 13, lineHeight: 20, color: colors.sec },
  policy: {
    marginTop: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    gap: 2,
    paddingVertical: spacing.xs,
  },
  policyText: { fontSize: 13.5, fontWeight: "600", color: colors.sec },
  pressed: { opacity: 0.6 },
  actions: { marginTop: spacing.md, gap: spacing.sm },
});
