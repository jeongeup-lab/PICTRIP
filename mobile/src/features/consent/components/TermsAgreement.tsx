import { useCallback, useState } from "react";
import { View, Text, Pressable, ScrollView, StyleSheet, Linking } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Icon } from "@/components/Icon";
import { ConsentDetail } from "@/features/consent/components/ConsentDetail";
import { ConsentRow } from "@/features/consent/components/ConsentRow";
import {
  EMPTY_CHOICES,
  TERMS_ITEMS,
  allChecked,
  requiredMet,
  setAll,
  type ConsentChoices,
} from "@/features/consent/lib/terms-items";
import { legalUrl } from "@/features/legal/constants";
import { colors, radii, spacing } from "@/constants/theme";

export const TERMS_TITLE = "PICTRIP 이용을 위해\n약관에 동의해 주세요";
export const TERMS_SUB = "[선택] 항목에 동의하지 않아도 서비스를 이용할 수 있어요.";
export const AGREE_ALL = "모두 동의합니다";
export const TERMS_CTA = "동의하고 시작하기";
export const TERMS_FOOT =
  "[선택] AI 질문 처리에 동의하면 여행 탭에서 자유 입력으로 물어볼 수 있어요. 동의하지 않으면 사진으로 찾기와 둘러보기만 이용돼요.";

export function TermsAgreement({ onDone }: { onDone: (choices: ConsentChoices) => void }) {
  const insets = useSafeAreaInsets();
  const [choices, setChoices] = useState<ConsentChoices>(EMPTY_CHOICES);

  const toggle = useCallback((key: keyof ConsentChoices) => {
    setChoices((prev) => ({ ...prev, [key]: !prev[key] }));
  }, []);

  const toggleAll = useCallback(() => {
    setChoices((prev) => setAll(!allChecked(prev)));
  }, []);

  const ready = requiredMet(choices);
  const everything = allChecked(choices);

  return (
    <View style={[styles.root, { paddingTop: insets.top + spacing.xl }]}>
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scroll}>
        <Text lineBreakStrategyIOS="hangul-word" style={styles.title}>
          {TERMS_TITLE}
        </Text>
        <Text lineBreakStrategyIOS="hangul-word" style={styles.sub}>
          {TERMS_SUB}
        </Text>

        <Pressable
          accessibilityRole="checkbox"
          accessibilityState={{ checked: everything }}
          accessibilityLabel={AGREE_ALL}
          onPress={toggleAll}
          style={({ pressed }) => [styles.all, pressed && styles.pressed]}
          testID="terms-agree-all"
        >
          <View style={[styles.check, everything && styles.checkOn]}>
            {everything ? (
              <Icon name="check" size={14} color={colors.onImage} strokeWidth={2.4} />
            ) : null}
          </View>
          <Text style={styles.allLabel}>{AGREE_ALL}</Text>
        </Pressable>

        <View style={styles.list}>
          {TERMS_ITEMS.map((item) => (
            <View key={item.key}>
              <ConsentRow
                required={item.required}
                label={item.label}
                checked={choices[item.key]}
                highlighted={item.key === "ai"}
                onToggle={() => toggle(item.key)}
                onSee={
                  item.doc ? () => void Linking.openURL(legalUrl(item.doc as never)) : undefined
                }
                testID={`terms-row-${item.key}`}
              />
              {item.key === "ai" ? (
                <View style={styles.detail}>
                  <ConsentDetail testID="terms-ai-detail" />
                </View>
              ) : null}
            </View>
          ))}
        </View>
      </ScrollView>

      <View style={[styles.foot, { paddingBottom: insets.bottom + spacing.md }]}>
        <Text lineBreakStrategyIOS="hangul-word" style={styles.footNote}>
          {TERMS_FOOT}
        </Text>
        <Pressable
          accessibilityRole="button"
          disabled={!ready}
          onPress={() => onDone(choices)}
          style={({ pressed }) => [styles.cta, !ready && styles.ctaOff, pressed && styles.pressed]}
          testID="terms-cta"
        >
          <Text style={styles.ctaLabel}>{TERMS_CTA}</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  scroll: { paddingHorizontal: spacing.lg, paddingBottom: spacing.lg },
  title: {
    fontSize: 22,
    lineHeight: 31,
    fontWeight: "800",
    letterSpacing: -0.6,
    color: colors.ink,
  },
  sub: { marginTop: 8, fontSize: 13.5, lineHeight: 20, color: colors.sec },
  all: {
    marginTop: spacing.lg,
    flexDirection: "row",
    alignItems: "center",
    gap: 11,
    paddingVertical: 15,
    paddingHorizontal: spacing.md,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: 14,
    backgroundColor: colors.fill,
  },
  allLabel: { flex: 1, fontSize: 15, fontWeight: "800", letterSpacing: -0.3, color: colors.ink },
  check: {
    width: 22,
    height: 22,
    borderRadius: 11,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1.5,
    borderColor: colors.line,
  },
  checkOn: { backgroundColor: colors.accent, borderColor: colors.accent },
  list: { marginTop: spacing.xs },
  detail: { marginHorizontal: spacing.md, marginBottom: spacing.sm },
  pressed: { opacity: 0.6 },
  foot: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.line,
  },
  footNote: { fontSize: 11.5, lineHeight: 17, color: colors.ter },
  cta: {
    marginTop: 11,
    height: 54,
    borderRadius: radii.md,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.accent,
  },
  ctaOff: { opacity: 0.4 },
  ctaLabel: { fontSize: 16, fontWeight: "700", color: colors.onImage },
});
