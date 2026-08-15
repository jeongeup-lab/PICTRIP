import { useCallback, useRef, useState } from "react";
import { View, Text, Pressable, ScrollView, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router, useNavigation } from "expo-router";
import { usePreventRemove } from "expo-router/react-navigation";
import { ScreenHeader } from "@/components/ScreenHeader";
import { InfoBox } from "@/components/InfoBox";
import { Icon } from "@/components/Icon";
import { PrimaryButton } from "@/components/PrimaryButton";
import { useAuthStore } from "@/features/auth/stores/auth-store";
import { accountDeletion } from "@/features/auth/account-deletion";
import { useSavedList } from "@/features/saved/queries";
import { colors, radii, spacing } from "@/constants/theme";

export default function AccountDeleteScreen() {
  const insets = useSafeAreaInsets();
  const navigation = useNavigation();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const deleteAccount = useAuthStore((state) => state.deleteAccount);
  const { data: saved } = useSavedList();
  const [acknowledged, setAcknowledged] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const deletionStarted = useRef(false);
  const allowLeave = useRef(false);
  const losses = accountDeletion.losses(saved?.length ?? 0);

  usePreventRemove(pending, ({ data }) => {
    if (allowLeave.current) navigation.dispatch(data.action);
  });

  const goBackOrAccount = useCallback(() => {
    if (router.canGoBack()) router.back();
    else router.replace("/account");
  }, []);

  const onDelete = async () => {
    if (!acknowledged || deletionStarted.current) return;
    deletionStarted.current = true;
    setPending(true);
    setError(null);
    try {
      await deleteAccount();
      allowLeave.current = true;
      setPending(false);
      router.dismissAll();
      router.replace("/(tabs)");
    } catch (caught) {
      setError(accountDeletion.errorMessage(caught));
      deletionStarted.current = false;
      setPending(false);
    }
  };

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <ScreenHeader title={accountDeletion.title} fallback="/account" disabled={pending} />
      {!isAuthenticated ? (
        <InfoBox
          title="로그인이 필요해요"
          text="회원 탈퇴는 로그인한 계정에서만 할 수 있어요."
          testID="delete-guest"
        >
          <View style={styles.keep}>
            <PrimaryButton label="계정으로 돌아가기" onPress={goBackOrAccount} />
          </View>
        </InfoBox>
      ) : (
        <ScrollView
          showsVerticalScrollIndicator={false}
          contentContainerStyle={[styles.scroll, { paddingBottom: spacing.lg + insets.bottom }]}
        >
          <View style={styles.content}>
            <Text lineBreakStrategyIOS="hangul-word" style={styles.lead}>
              {accountDeletion.lead}
            </Text>
            <View style={styles.losses} testID="delete-consequences">
              {losses.map((loss) => (
                <View key={loss} style={styles.loss}>
                  <Icon name="close" size={17} color={colors.danger} />
                  <Text lineBreakStrategyIOS="hangul-word" style={styles.lossText}>
                    {loss}
                  </Text>
                </View>
              ))}
            </View>
            <Pressable
              accessibilityRole="checkbox"
              accessibilityLabel="탈퇴 후 데이터를 복구할 수 없음을 확인"
              accessibilityState={{ checked: acknowledged }}
              disabled={pending}
              onPress={() => setAcknowledged((current) => !current)}
              style={({ pressed }) => [styles.acknowledgement, pressed && styles.pressed]}
              testID="delete-acknowledgement"
            >
              <View style={[styles.check, acknowledged && styles.checked]}>
                {acknowledged ? <Icon name="check" size={14} color={colors.onImage} /> : null}
              </View>
              <Text lineBreakStrategyIOS="hangul-word" style={styles.acknowledgementText}>
                {accountDeletion.acknowledgement}
              </Text>
            </Pressable>
            {error ? <Text style={styles.error}>{error}</Text> : null}
          </View>
          <View style={styles.actions}>
            <PrimaryButton
              label="계정 유지하기"
              variant="secondary"
              disabled={pending}
              onPress={goBackOrAccount}
            />
            <Pressable
              accessibilityRole="button"
              disabled={!acknowledged || pending}
              onPress={() => void onDelete()}
              style={({ pressed }) => [
                styles.delete,
                (!acknowledged || pending) && styles.deleteDisabled,
                pressed && acknowledged && !pending && styles.pressed,
              ]}
              testID="delete-account"
            >
              <Text style={styles.deleteText}>{pending ? "탈퇴 처리 중…" : "탈퇴하기"}</Text>
            </Pressable>
          </View>
        </ScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  scroll: { flexGrow: 1, justifyContent: "space-between", padding: spacing.lg },
  content: { gap: spacing.xl },
  lead: {
    marginTop: spacing.sm,
    fontSize: 22,
    lineHeight: 30,
    fontWeight: "800",
    letterSpacing: -0.5,
    color: colors.ink,
  },
  losses: { gap: spacing.md },
  loss: { flexDirection: "row", alignItems: "center", gap: 11 },
  lossText: { flex: 1, fontSize: 15, lineHeight: 22, fontWeight: "600", color: colors.ink },
  acknowledgement: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    paddingVertical: spacing.sm,
    borderRadius: radii.md,
  },
  acknowledgementText: { flex: 1, fontSize: 14, lineHeight: 21, color: colors.sec },
  check: {
    width: 22,
    height: 22,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.sec,
    borderRadius: radii.sm,
  },
  checked: { borderColor: colors.accent, backgroundColor: colors.accent },
  error: { fontSize: 13, lineHeight: 19, color: colors.accentText },
  actions: { gap: spacing.sm, paddingTop: spacing.xl },
  keep: { marginTop: spacing.md },
  delete: {
    height: 54,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: radii.md,
    backgroundColor: colors.accent,
  },
  deleteDisabled: { opacity: 0.4 },
  deleteText: { fontSize: 16, fontWeight: "700", color: colors.onImage },
  pressed: { opacity: 0.72 },
});
