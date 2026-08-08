import { useCallback, useState } from "react";
import { View, Text, Pressable, ScrollView, Linking, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router, useFocusEffect } from "expo-router";
import { Icon } from "@/components/Icon";
import { ListGroup } from "@/components/ListGroup";
import { ListRow } from "@/components/ListRow";
import { SectionTitle } from "@/components/SectionTitle";
import { InfoBox } from "@/components/InfoBox";
import { useAuthStore } from "@/features/auth/stores/auth-store";
import { useSavedList } from "@/features/saved/queries";
import { SavedRail } from "@/features/saved/components/SavedRail";
import { EmptyBoard } from "@/features/saved/components/EmptyBoard";
import { prefetchSpot } from "@/features/spots/queries";
import { ProfileHero } from "@/features/profile/components/ProfileHero";
import { GuestHero } from "@/features/profile/components/GuestHero";
import { StatTiles } from "@/features/profile/components/StatTiles";
import { profileStats } from "@/features/profile/lib/stats";
import { PERM_LABEL, useAppPermissions } from "@/features/profile/hooks/use-app-permissions";
import { APP_VERSION } from "@/lib/app-meta";
import { colors, spacing } from "@/constants/theme";

export const GUEST_NOTICE =
  "검색 · 지도 · 사진으로 찾기는 그대로 쓸 수 있어요. 스크랩과 기록만 계정이 필요해요.";

export default function ProfileTab() {
  const insets = useSafeAreaInsets();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const user = useAuthStore((s) => s.user);
  const { data: saved } = useSavedList();
  const { location } = useAppPermissions();
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
      <View style={styles.nav}>
        <Text style={styles.navTitle}>마이</Text>
        <Pressable
          accessibilityRole="button"
          hitSlop={8}
          style={styles.navBtn}
          onPress={() => router.push("/settings")}
          testID="open-settings"
        >
          <Icon name="settings" size={20} color={colors.ink} />
        </Pressable>
      </View>

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scroll}>
        {isAuthenticated && user ? (
          <ProfileHero user={user} onPress={() => router.push("/account")} />
        ) : (
          <GuestHero onPress={() => router.push("/auth/login")} />
        )}

        <StatTiles stats={stats} onPressSaved={() => router.push("/saved")} />

        {!isAuthenticated ? <InfoBox title="로그인 없이도 되는 것" text={GUEST_NOTICE} /> : null}

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
                actionLabel="둘러보러 가기"
                actionIcon="home"
                onAction={() => router.push("/(tabs)")}
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
            icon="map-pin"
            title="위치 권한"
            value={location ? PERM_LABEL[location] : null}
            tone={location === "granted" ? "on" : "off"}
            chevron
            onPress={() => void Linking.openSettings()}
          />
          <ListRow
            icon="bell"
            title="알림·권한 설정"
            chevron
            onPress={() => router.push("/settings")}
          />
          <ListRow
            icon="shield-check"
            title="약관·정책"
            chevron
            onPress={() => router.push("/legal")}
          />
          <ListRow icon="info" title="앱 버전" value={APP_VERSION} />
        </ListGroup>

        <Text style={styles.foot}>관광 정보 출처 · 한국관광공사 TourAPI</Text>
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
    justifyContent: "space-between",
    paddingHorizontal: spacing.lg,
  },
  navTitle: { fontSize: 21, fontWeight: "800", letterSpacing: -0.5, color: colors.ink },
  navBtn: { width: 34, height: 34, alignItems: "flex-end", justifyContent: "center" },
  scroll: { paddingBottom: spacing.xxl },
  foot: {
    marginTop: spacing.lg,
    paddingHorizontal: spacing.lg,
    fontSize: 11.5,
    color: colors.ter,
  },
});
