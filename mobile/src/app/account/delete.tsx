import { useCallback, useRef, useState } from "react";
import { View, ScrollView, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router, useNavigation } from "expo-router";
import { usePreventRemove } from "expo-router/react-navigation";
import { ScreenHeader } from "@/components/ScreenHeader";
import { SectionTitle } from "@/components/SectionTitle";
import { ListGroup } from "@/components/ListGroup";
import { ListRow } from "@/components/ListRow";
import { InfoBox } from "@/components/InfoBox";
import { Icon } from "@/components/Icon";
import { PrimaryButton } from "@/components/PrimaryButton";
import { useAuthStore } from "@/features/auth/stores/auth-store";
import { accountDeletion } from "@/features/auth/account-deletion";
import { DeleteConfirmSheet } from "@/features/auth/components/DeleteConfirmSheet";
import { colors, spacing } from "@/constants/theme";

function Radio({ selected }: { selected: boolean }) {
  return (
    <View style={[styles.radio, selected && styles.radioSelected]}>
      {selected ? <Icon name="check" size={14} color={colors.onImage} /> : null}
    </View>
  );
}

export default function AccountDeleteScreen() {
  const insets = useSafeAreaInsets();
  const navigation = useNavigation();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const deleteAccount = useAuthStore((state) => state.deleteAccount);
  const [reason, setReason] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const deletionStarted = useRef(false);
  const allowLeave = useRef(false);

  usePreventRemove(pending, ({ data }) => {
    if (allowLeave.current) navigation.dispatch(data.action);
  });

  const goBackOrAccount = useCallback(() => {
    if (router.canGoBack()) router.back();
    else router.replace("/account");
  }, []);

  const onDelete = async () => {
    if (deletionStarted.current) return;
    deletionStarted.current = true;
    setPending(true);
    setError(null);
    try {
      await deleteAccount(reason ?? undefined);
      allowLeave.current = true;
      setPending(false);
      setConfirming(false);
      router.dismissAll();
      router.replace("/(tabs)");
    } catch (caught) {
      setError(accountDeletion.errorMessage(caught));
      deletionStarted.current = false;
      setPending(false);
    }
  };

  if (!isAuthenticated) {
    return (
      <View style={[styles.root, { paddingTop: insets.top }]}>
        <ScreenHeader title={accountDeletion.title} fallback="/account" />
        <InfoBox
          title="로그인이 필요해요"
          text="회원 탈퇴는 로그인한 계정에서만 할 수 있어요."
          testID="delete-guest"
        >
          <View style={styles.guestAction}>
            <PrimaryButton label="계정으로 돌아가기" onPress={goBackOrAccount} />
          </View>
        </InfoBox>
      </View>
    );
  }

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <ScreenHeader title={accountDeletion.title} fallback="/account" disabled={pending} />
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scroll}>
        <SectionTitle title={accountDeletion.reasonPrompt} />
        <ListGroup dividerInset={0}>
          {accountDeletion.reasons.map((item) => (
            <ListRow
              key={item.code}
              title={item.label}
              right={<Radio selected={reason === item.code} />}
              onPress={() => setReason((current) => (current === item.code ? null : item.code))}
              testID={`delete-reason-${item.code}`}
            />
          ))}
        </ListGroup>
      </ScrollView>
      <View style={[styles.actions, { paddingBottom: insets.bottom + spacing.lg }]}>
        <PrimaryButton
          label={accountDeletion.submitLabel}
          disabled={pending}
          onPress={() => setConfirming(true)}
          testID="delete-account"
        />
      </View>
      <DeleteConfirmSheet
        visible={confirming}
        pending={pending}
        error={error}
        onConfirm={() => void onDelete()}
        onCancel={() => {
          if (pending) return;
          setError(null);
          setConfirming(false);
        }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  scroll: { paddingBottom: spacing.xxl },
  guestAction: { marginTop: spacing.md },
  actions: { paddingHorizontal: spacing.md, paddingTop: spacing.md },
  radio: {
    width: 22,
    height: 22,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.sec,
    borderRadius: 11,
  },
  radioSelected: { borderColor: colors.accent, backgroundColor: colors.accent },
});
