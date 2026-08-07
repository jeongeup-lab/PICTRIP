import { useState } from "react";
import { View, Text, Pressable, ScrollView, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router } from "expo-router";
import { Icon } from "@/components/Icon";
import { ListGroup } from "@/components/ListGroup";
import { ListRow } from "@/components/ListRow";
import { InfoBox } from "@/components/InfoBox";
import { PrimaryButton } from "@/components/PrimaryButton";
import { useAuthStore } from "@/features/auth/stores/auth-store";
import { AppError } from "@/lib/app-error";
import { colors, spacing } from "@/constants/theme";

export const DELETE_TITLE = "회원 탈퇴";
export const DELETE_LEAD = "다음 항목이 즉시 삭제되고 되돌릴 수 없어요.";
export const DELETE_EXPORT_HINT = "탈퇴 전 스크랩을 CSV로 내보낼 수 있어요. 설정 > 내 데이터.";

function formatDate(value: string | null): string | null {
  const date = value?.slice(0, 10);
  return date && /^\d{4}-\d{2}-\d{2}$/.test(date) ? date.replace(/-/g, ".") : null;
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
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const joined = formatDate(user?.createdAt ?? null);

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
      router.back();
    } catch (e) {
      setError(deleteErrorMessage(e));
    } finally {
      setBusy(false);
    }
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
                  {["저장한 모든 스크랩", "계정 정보와 로그인 연결", "취향 데이터"].map((item) => (
                    <View key={item} style={styles.checkItem}>
                      <Icon name="close" size={14} color={colors.accent} />
                      <Text style={styles.checkText}>{item}</Text>
                    </View>
                  ))}
                </View>
                {error ? <Text style={styles.error}>{error}</Text> : null}
                <View style={styles.actions}>
                  <View style={styles.actionHalf}>
                    <PrimaryButton
                      label="취소"
                      variant="secondary"
                      disabled={busy}
                      onPress={() => setConfirming(false)}
                    />
                  </View>
                  <View style={styles.actionHalf}>
                    <PrimaryButton
                      label="탈퇴하기"
                      disabled={busy}
                      onPress={() => void onDelete()}
                      testID="confirm-delete"
                    />
                  </View>
                </View>
              </InfoBox>
            ) : null}

            <Text style={styles.foot}>{DELETE_EXPORT_HINT}</Text>
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
  actions: { flexDirection: "row", gap: 9, marginTop: spacing.md },
  actionHalf: { flex: 1 },
  foot: {
    marginTop: spacing.md,
    paddingHorizontal: spacing.lg,
    fontSize: 11.5,
    lineHeight: 17,
    color: colors.ter,
  },
});
