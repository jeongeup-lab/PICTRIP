import { View, Text, Pressable, ScrollView, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router } from "expo-router";
import { Icon } from "@/components/Icon";
import { TERMS_VERSION } from "@/constants/legal";
import { useConsents, useUpdateConsent } from "@/features/consent/queries";
import { useLocationConsentSync } from "@/features/consent/hooks/use-location-consent-sync";
import { localDateLabel } from "@/lib/local-date";
import { colors, radii, spacing } from "@/constants/theme";

export default function ConsentScreen() {
  const insets = useSafeAreaInsets();
  const { data, isLoading, isError, refetch } = useConsents();
  const update = useUpdateConsent();

  useLocationConsentSync(data);

  const reConsent = () => {
    if (!data) return;
    update.mutate({
      locationConsent: data.locationConsent,
      termsVersion: TERMS_VERSION,
    });
  };

  const isCurrent = data?.termsVersion === TERMS_VERSION;
  const consentedDate = localDateLabel(data?.consentedAt);

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
              <View style={styles.row}>
                <View style={styles.rowMain}>
                  <Text style={styles.label}>위치정보 수집·이용 동의</Text>
                  <Text style={styles.sub}>
                    내 주변 추천에 사용해요. 허용 여부는 설정 › 권한에서 바꿀 수 있어요.
                  </Text>
                </View>
                <Text style={[styles.value, data.locationConsent && styles.valueOn]}>
                  {data.locationConsent ? "동의함" : "동의 안 함"}
                </Text>
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
                  <View style={styles.currentBadge}>
                    <Text style={styles.currentBadgeText}>최신</Text>
                  </View>
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
  valueOn: { color: colors.accentText, fontWeight: "700" },
  currentBadge: {
    backgroundColor: colors.accentFill,
    borderRadius: radii.pill,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  currentBadgeText: { fontSize: 12, fontWeight: "700", color: colors.accentText },
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
