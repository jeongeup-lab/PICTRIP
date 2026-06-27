import { View, Text, Pressable, ScrollView, Alert, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router } from "expo-router";
import { Icon } from "@/components/Icon";
import { useAuthStore } from "@/features/auth/stores/auth-store";
import { useSavedList } from "@/features/saved/queries";
import { prefetchSpot } from "@/features/spots/queries";
import { SavedRail } from "@/features/saved/components/SavedRail";
import { EmptyBoard } from "@/features/saved/components/EmptyBoard";
import { ProfileHeader } from "@/features/profile/components/ProfileHeader";
import { GuestLoginRow } from "@/features/profile/components/GuestLoginRow";
import { SettingsRows } from "@/features/profile/components/SettingsRows";
import { colors, spacing } from "@/constants/theme";

export default function ProfileTab() {
  const insets = useSafeAreaInsets();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const deleteAccount = useAuthStore((s) => s.deleteAccount);
  const { data: saved } = useSavedList();

  const confirmDelete = () =>
    Alert.alert("회원 탈퇴", "탈퇴하면 스크랩과 계정 정보가 삭제돼요. 계속할까요?", [
      { text: "취소", style: "cancel" },
      { text: "탈퇴", style: "destructive", onPress: () => void deleteAccount() },
    ]);

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <View style={styles.nav}>
        <Text style={styles.navTitle}>마이</Text>
      </View>

      <ScrollView showsVerticalScrollIndicator={false}>
        {isAuthenticated && user ? (
          <ProfileHeader user={user} />
        ) : (
          <GuestLoginRow onPress={() => router.push("/auth/login")} />
        )}

        <View style={styles.sep} />

        <View style={styles.scrapWrap}>
          <View style={styles.secHead}>
            <Text style={styles.secTitle}>스크랩</Text>
            {isAuthenticated && saved && saved.length > 0 ? (
              <Pressable style={styles.seeAll} onPress={() => router.push("/saved")}>
                <Text style={styles.seeAllText}>전체보기</Text>
                <Icon name="chevron-right" size={15} color={colors.sec} />
              </Pressable>
            ) : null}
          </View>

          {isAuthenticated ? (
            saved && saved.length > 0 ? (
              <SavedRail
                spots={saved}
                onPressItem={(id) => {
                  prefetchSpot(id);
                  router.push(`/spots/${id}`);
                }}
              />
            ) : (
              <EmptyBoard
                text="아직 스크랩한 곳이 없어요"
                actionLabel="둘러보러 가기"
                actionIcon="home"
                onAction={() => router.push("/(tabs)")}
              />
            )
          ) : (
            <EmptyBoard
              text="로그인하고 마음에 든 곳을 스크랩하세요"
              actionLabel="로그인하기"
              actionIcon="log-in"
              onAction={() => router.push("/auth/login")}
            />
          )}
        </View>

        <View style={styles.sep} />

        <SettingsRows onLogout={isAuthenticated ? () => void logout() : undefined} />

        <View style={styles.foot}>
          <Pressable onPress={() => router.push("/legal")}>
            <Text style={styles.footLink}>약관·정책</Text>
          </Pressable>
          {isAuthenticated ? (
            <>
              <View style={styles.footDiv} />
              <Pressable onPress={confirmDelete}>
                <Text style={styles.footLink}>회원 탈퇴</Text>
              </Pressable>
            </>
          ) : null}
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.inset },
  nav: { height: 50, alignItems: "center", justifyContent: "center", backgroundColor: colors.bg },
  navTitle: { fontSize: 17, fontWeight: "700", color: colors.ink },
  sep: { height: 9, backgroundColor: colors.inset },
  scrapWrap: { backgroundColor: colors.bg, paddingBottom: 2 },
  secHead: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: 11,
  },
  secTitle: { fontSize: 18, fontWeight: "800", letterSpacing: -0.3, color: colors.ink },
  seeAll: { flexDirection: "row", alignItems: "center", gap: 3 },
  seeAllText: { color: colors.sec, fontSize: 13.5, fontWeight: "600" },
  foot: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 16,
    paddingVertical: 24,
    paddingBottom: 30,
  },
  footLink: { color: colors.sec, fontSize: 13, fontWeight: "600" },
  footDiv: { width: 1, height: 12, backgroundColor: colors.line },
});
