import { useState } from "react";
import { Alert, View, Text, Pressable, ScrollView, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router } from "expo-router";
import { Icon } from "@/components/Icon";
import { ListGroup } from "@/components/ListGroup";
import { ListRow } from "@/components/ListRow";
import { InfoBox } from "@/components/InfoBox";
import { PrimaryButton } from "@/components/PrimaryButton";
import { useAuthStore } from "@/features/auth/stores/auth-store";
import { useSavedList } from "@/features/saved/queries";
import { AppError } from "@/lib/app-error";
import { localDateLabel } from "@/lib/local-date";
import { colors, spacing } from "@/constants/theme";

export const DELETE_TITLE = "회원 탈퇴";
export const DELETE_LEAD = "탈퇴하면 다음이 즉시 사라지고 되돌릴 수 없어요.";

export function deleteLosses(savedCount: number): string[] {
  return [
    savedCount > 0 ? `스크랩 ${savedCount}개가 삭제돼요` : "스크랩이 모두 삭제돼요",
    "소셜 로그인 연결이 해제돼요",
    "닉네임·이메일 등 계정 정보가 지워져요",
  ];
}

function deleteErrorMessage(error: unknown): string {
  if (error instanceof AppError && error.code === "AUTH_TOKEN_INVALID") {
    return "로그인이 만료됐어요. 다시 로그인한 뒤 시도해 주세요.";
  }
  if (error instanceof AppError && error.code === "NETWORK_ERROR") {
    return "네트워크가 불안정해요. 잠시 후 다시 시도해 주세요.";
  }
  return "탈퇴 처리에 실패했어요. 잠시 후 다시 시도해 주세요.";
}

export default function AccountScreen() {
  const insets = useSafeAreaInsets();
  const user = useAuthStore((s) => s.user);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const logout = useAuthStore((s) => s.logout);
  const deleteAccount = useAuthStore((s) => s.deleteAccount);
  const { data: saved } = useSavedList();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const joined = localDateLabel(user?.createdAt);
  const losses = deleteLosses(saved?.length ?? 0);

  const onLogout = async () => {
    setBusy(true);
    await logout();
    setBusy(false);
    router.back();
  };

  const onDelete = async () => {
    setBusy(true);
    setError(null);
    try {
      await deleteAccount();
      Alert.alert("탈퇴가 완료됐어요", "그동안 이용해 주셔서 고마워요.", [
        { text: "확인", onPress: () => router.replace("/(tabs)") },
      ]);
    } catch (e) {
      setError(deleteErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const confirmDelete = () => {
    Alert.alert("정말 탈퇴하시겠어요?", "삭제된 계정과 스크랩은 되돌릴 수 없어요.", [
      { text: "취소", style: "cancel" },
      { text: "탈퇴하기", style: "destructive", onPress: () => void onDelete() },
    ]);
  };

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <View style={styles.nav}>
        <Pressable style={styles.navBtn} onPress={() => router.back()} hitSlop={8}>
          <Icon name="chevron-left" size={23} />
        </Pressable>
        <Text style={styles.title}>계정</Text>
      </View>

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scroll}>
        {!isAuthenticated || !user ? (
          <InfoBox
            title="로그인이 필요해요"
            text="계정 정보는 로그인한 뒤에 볼 수 있어요."
            testID="account-guest"
          >
            <View style={styles.action}>
              <PrimaryButton label="로그인하기" onPress={() => router.push("/auth/login")} />
            </View>
          </InfoBox>
        ) : (
          <>
            <ListGroup style={styles.firstGroup}>
              <ListRow title="닉네임" value={user.displayName ?? "여행자"} />
              <ListRow title="이메일" value={user.email ?? "연결된 이메일 없음"} />
              <ListRow title="가입일" value={joined ?? "—"} />
            </ListGroup>

            <ListGroup style={styles.group}>
              <ListRow
                icon="log-out"
                title="로그아웃"
                onPress={() => void onLogout()}
                testID="logout"
              />
            </ListGroup>

            <ListGroup style={styles.group}>
              <ListRow
                icon="user-x"
                title={DELETE_TITLE}
                danger
                onPress={() => setConfirming(true)}
                testID="open-delete"
              />
            </ListGroup>

            {confirming ? (
              <InfoBox
                title={DELETE_TITLE}
                text={DELETE_LEAD}
                tone="danger"
                testID="delete-confirm"
              >
                <View style={styles.checklist}>
                  {losses.map((item) => (
                    <View key={item} style={styles.checkItem}>
                      <Icon name="close" size={14} color={colors.danger} />
                      <Text style={styles.checkText}>{item}</Text>
                    </View>
                  ))}
                </View>
                {error ? <Text style={styles.error}>{error}</Text> : null}
                <View style={styles.actions}>
                  <PrimaryButton
                    label="계정 유지하기"
                    disabled={busy}
                    onPress={() => setConfirming(false)}
                  />
                  <Pressable
                    style={styles.destructive}
                    disabled={busy}
                    onPress={confirmDelete}
                    hitSlop={8}
                    testID="confirm-delete"
                  >
                    <Text style={[styles.destructiveText, busy && styles.destructiveBusy]}>
                      {busy ? "탈퇴 처리 중…" : "탈퇴하기"}
                    </Text>
                  </Pressable>
                </View>
              </InfoBox>
            ) : null}
          </>
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  nav: {
    height: 50,
    flexDirection: "row",
    alignItems: "center",
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  navBtn: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
  title: {
    position: "absolute",
    left: 0,
    right: 0,
    textAlign: "center",
    fontSize: 17,
    fontWeight: "700",
    color: colors.ink,
  },
  scroll: { paddingBottom: spacing.xxl },
  firstGroup: { marginTop: spacing.md },
  group: { marginTop: spacing.md },
  action: { marginTop: spacing.md },
  checklist: { marginTop: spacing.md, gap: 7 },
  checkItem: { flexDirection: "row", alignItems: "center", gap: 9 },
  checkText: { fontSize: 13, color: colors.sec },
  error: { marginTop: spacing.md, fontSize: 12.5, color: colors.accentText },
  actions: { marginTop: spacing.md, gap: spacing.xs },
  destructive: { alignSelf: "center", paddingVertical: 12, paddingHorizontal: spacing.lg },
  destructiveText: { fontSize: 14.5, fontWeight: "700", color: colors.danger },
  destructiveBusy: { opacity: 0.4 },
});
