import { View, ScrollView, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router } from "expo-router";
import { ScreenHeader } from "@/components/ScreenHeader";
import { ListGroup } from "@/components/ListGroup";
import { ListRow } from "@/components/ListRow";
import { InfoBox } from "@/components/InfoBox";
import { PrimaryButton } from "@/components/PrimaryButton";
import { useAuthStore } from "@/features/auth/stores/auth-store";
import { accountDeletion } from "@/features/auth/account-deletion";
import { localDateLabel } from "@/lib/local-date";
import { colors, spacing } from "@/constants/theme";

export default function AccountScreen() {
  const insets = useSafeAreaInsets();
  const user = useAuthStore((s) => s.user);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const logout = useAuthStore((s) => s.logout);
  const joined = localDateLabel(user?.createdAt);

  const onLogout = async () => {
    await logout();
    router.back();
  };

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <ScreenHeader title="계정" fallback="/(tabs)/profile" />

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
                title={accountDeletion.title}
                danger
                onPress={() => router.push("/account/delete")}
                testID="open-delete"
              />
            </ListGroup>
          </>
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  scroll: { paddingBottom: spacing.xxl },
  firstGroup: { marginTop: spacing.md },
  group: { marginTop: spacing.md },
  action: { marginTop: spacing.md },
});
