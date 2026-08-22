import { useCallback, useState } from "react";
import { View, Pressable, ScrollView, StyleSheet, NativeModules } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import * as WebBrowser from "expo-web-browser";
import { router, useFocusEffect } from "expo-router";
import { Icon } from "@/components/Icon";
import { ListGroup } from "@/components/ListGroup";
import { ListRow } from "@/components/ListRow";
import { SectionTitle } from "@/components/SectionTitle";
import { useAuthStore } from "@/features/auth/stores/auth-store";
import { useSavedList } from "@/features/saved/queries";
import { SavedRail } from "@/features/saved/components/SavedRail";
import { EmptyBoard } from "@/features/saved/components/EmptyBoard";
import { prefetchSpot } from "@/features/spots/queries";
import { ProfileHero } from "@/features/profile/components/ProfileHero";
import { GuestHero } from "@/features/profile/components/GuestHero";
import { StatTiles } from "@/features/profile/components/StatTiles";
import { profileStats } from "@/features/profile/lib/stats";
import { APP_BUILD_LABEL } from "@/lib/app-meta";
import * as Updates from "expo-updates";
import { colors, spacing, themeName, setThemeOverride } from "@/constants/theme";

const SUPPORT_URL = "https://pictrip.org/support";

export default function ProfileTab() {
  const insets = useSafeAreaInsets();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const user = useAuthStore((s) => s.user);
  const { data: saved } = useSavedList();
  const [today, setToday] = useState(() => Date.now());
  useFocusEffect(
    useCallback(() => {
      setToday(Date.now());
    }, []),
  );

  const stats = isAuthenticated ? profileStats(saved, user?.createdAt, today) : null;
  const scraps = saved ?? [];

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <View style={styles.nav} testID="profile-nav">
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={themeName === "dark" ? "라이트 모드로 전환" : "다크 모드로 전환"}
          hitSlop={8}
          style={styles.navBtn}
          onPress={() => {
            void (async () => {
              await setThemeOverride(themeName === "dark" ? "light" : "dark");
              if (Updates.isEnabled) {
                await Updates.reloadAsync();
              } else {
                (NativeModules.DevSettings as { reload?: () => void } | undefined)?.reload?.();
              }
            })();
          }}
          testID="theme-toggle"
        >
          <Icon name={themeName === "dark" ? "sun" : "moon"} size={20} color={colors.ink} />
        </Pressable>
      </View>

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scroll}>
        {isAuthenticated && user ? (
          <ProfileHero user={user} onPress={() => router.push("/account")} />
        ) : (
          <GuestHero onPress={() => router.push("/auth/login")} />
        )}

        <StatTiles stats={stats} onPressSaved={() => router.push("/saved")} />

        {isAuthenticated ? (
          <>
            <SectionTitle
              title="스크랩"
              actionLabel={scraps.length > 0 ? `전체 ${scraps.length}` : undefined}
              onAction={scraps.length > 0 ? () => router.push("/saved") : undefined}
              testID="see-all-saved"
            />
            {scraps.length > 0 ? (
              <SavedRail
                spots={scraps}
                onPressItem={(spot) => {
                  prefetchSpot(spot);
                  router.push(`/spots/${spot.contentId}`);
                }}
              />
            ) : (
              <EmptyBoard
                text="아직 스크랩한 곳이 없어요"
                actionLabel="탐색 탭 열기"
                actionIcon="search"
                onAction={() => router.navigate("/(tabs)/explore")}
              />
            )}
          </>
        ) : null}

        <SectionTitle title="설정" />
        <ListGroup>
          {isAuthenticated ? (
            <ListRow icon="person" title="계정" chevron onPress={() => router.push("/account")} />
          ) : null}
          <ListRow
            icon="settings"
            title="기기 권한"
            chevron
            onPress={() => router.push("/settings")}
          />
          {isAuthenticated ? (
            <ListRow
              icon="check"
              title="동의 내역"
              chevron
              onPress={() => router.push("/consent")}
            />
          ) : null}
          <ListRow
            icon="shield-check"
            title="약관·정책"
            chevron
            onPress={() => router.push("/legal")}
          />
          <ListRow
            icon="chat"
            title="문의"
            chevron
            onPress={() => void WebBrowser.openBrowserAsync(SUPPORT_URL)}
          />
          <ListRow icon="info" title="앱 버전" value={APP_BUILD_LABEL} />
        </ListGroup>
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
    justifyContent: "flex-end",
    paddingHorizontal: spacing.lg,
  },
  navBtn: { width: 48, height: 48, alignItems: "center", justifyContent: "center" },
  scroll: { paddingBottom: spacing.xxl },
});
