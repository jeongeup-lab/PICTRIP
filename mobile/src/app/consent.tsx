import { useCallback } from "react";
import { View, Text, Pressable, ScrollView, Switch, Linking, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router, useFocusEffect } from "expo-router";
import * as Location from "expo-location";
import { Icon } from "@/components/Icon";
import { TERMS_VERSION } from "@/constants/legal";
import { useConsents, useUpdateConsent } from "@/features/consent/queries";
import { buildConsentPut } from "@/features/consent/lib/build-consent-put";
import { colors, spacing } from "@/constants/theme";

export default function ConsentScreen() {
  const insets = useSafeAreaInsets();
  const { data, isLoading, isError, refetch } = useConsents();
  const update = useUpdateConsent();

  // Focus-local location-permission re-sync (S01 §4; global AppState hook deferred).
  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      void (async () => {
        if (!data) return;
        const perm = await Location.getForegroundPermissionsAsync();
        if (!cancelled && perm.granted !== data.locationConsent) {
          update.mutate(buildConsentPut(data, perm.granted, data.termsVersion ?? TERMS_VERSION));
        }
      })();
      return () => {
        cancelled = true;
      };
    }, [data, update]),
  );

  const togglePhoto = (next: boolean) => {
    if (!data) return;
    update.mutate({
      locationConsent: data.locationConsent,
      photoConsent: next,
      termsVersion: data.termsVersion ?? TERMS_VERSION,
    });
  };

  const reConsent = () => {
    if (!data) return;
    update.mutate({
      locationConsent: data.locationConsent,
      photoConsent: data.photoConsent,
      termsVersion: TERMS_VERSION,
    });
  };

  const isCurrent = data?.termsVersion === TERMS_VERSION;
  const consentedDate = data?.consentedAt ? data.consentedAt.slice(0, 10).replace(/-/g, ".") : null;

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <View style={styles.nav}>
        <Pressable style={styles.navBtn} onPress={() => router.back()} hitSlop={8}>
          <Icon name="chevron-left" size={23} />
        </Pressable>
        <Text style={styles.title}>동의 관리</Text>
      </View>

      <ScrollView showsVerticalScrollIndicator={false}>
        {isLoading ? (
          <Text style={styles.note}>불러오는 중…</Text>
        ) : isError || !data ? (
          <View style={styles.errBox}>
            <Text style={styles.note}>동의 정보를 불러오지 못했어요</Text>
            <Pressable onPress={() => void refetch()} hitSlop={8}>
              <Text style={styles.retry}>재시도</Text>
            </Pressable>
          </View>
        ) : (
          <>
            <View style={styles.group}>
              <Pressable style={styles.row} onPress={() => Linking.openSettings()}>
                <View style={styles.rowMain}>
                  <Text style={styles.label}>위치정보 수집·이용 동의</Text>
                  <Text style={styles.sub}>
                    내 주변 추천에 사용해요. 기기 설정에서 변경할 수 있어요.
                  </Text>
                </View>
                <Text style={styles.value}>{data.locationConsent ? "허용" : "거부"}</Text>
                <Icon name="chevron-right" size={20} color={colors.ter} />
              </Pressable>
            </View>

            <View style={styles.group}>
              <View style={styles.row}>
                <View style={styles.rowMain}>
                  <Text style={styles.label}>사진 분석 이용 동의</Text>
                  <Text style={styles.sub}>
                    사진 검색 시 이미지는 기기에서 분석 후 즉시 폐기되며 저장하지 않아요.
                  </Text>
                </View>
                <Switch
                  value={data.photoConsent}
                  onValueChange={togglePhoto}
                  trackColor={{ false: colors.line, true: colors.ink }}
                />
              </View>
            </View>

            <View style={styles.group}>
              <View style={styles.row}>
                <View style={styles.rowMain}>
                  <Text style={styles.label}>약관·개인정보 동의</Text>
                  <Text style={styles.sub}>
                    버전 {data.termsVersion ?? "—"}
                    {consentedDate ? ` · ${consentedDate}` : ""}
                  </Text>
                </View>
                {isCurrent ? (
                  <Text style={styles.value}>최신</Text>
                ) : (
                  <Pressable style={styles.reBtn} onPress={reConsent} hitSlop={8}>
                    <Text style={styles.reBtnText}>재동의</Text>
                  </Pressable>
                )}
              </View>
              <Pressable style={styles.linkRow} onPress={() => router.push("/legal")}>
                <Text style={styles.linkText}>약관·정책 보기</Text>
                <Icon name="chevron-right" size={18} color={colors.ter} />
              </Pressable>
            </View>
          </>
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.inset },
  nav: {
    height: 50,
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.bg,
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
  group: { backgroundColor: colors.bg, marginTop: 9 },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingVertical: 16,
    paddingHorizontal: spacing.lg,
  },
  rowMain: { flex: 1, gap: 4 },
  label: { fontSize: 15.5, fontWeight: "600", color: colors.ink },
  sub: { fontSize: 12.5, lineHeight: 18, color: colors.ter },
  value: { fontSize: 14, color: colors.ter },
  reBtn: {
    paddingHorizontal: spacing.md,
    paddingVertical: 7,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.line,
  },
  reBtnText: { fontSize: 13, fontWeight: "700", color: colors.ink },
  linkRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: 14,
    paddingHorizontal: spacing.lg,
    borderTopWidth: 1,
    borderTopColor: colors.line,
  },
  linkText: { fontSize: 14, color: colors.sec, fontWeight: "600" },
  note: { textAlign: "center", color: colors.ter, fontSize: 14, marginTop: spacing.xxl },
  errBox: { alignItems: "center", gap: spacing.md, marginTop: spacing.xxl },
  retry: { color: colors.ink, fontSize: 14, fontWeight: "700" },
});
