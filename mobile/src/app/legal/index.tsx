import { View, Text, Pressable, ScrollView, Switch, Linking, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router } from "expo-router";
import { Icon } from "@/components/Icon";
import { ListGroup } from "@/components/ListGroup";
import { ListRow } from "@/components/ListRow";
import { SectionTitle } from "@/components/SectionTitle";
import { LEGAL_DOCS } from "@/features/legal/constants";
import { useAuthStore } from "@/features/auth/stores/auth-store";
import { useConsents, useUpdateConsent } from "@/features/consent/queries";
import { useLocationConsentSync } from "@/features/consent/hooks/use-location-consent-sync";
import { TERMS_VERSION } from "@/constants/legal";
import { localDateLabel } from "@/lib/local-date";
import { colors, spacing } from "@/constants/theme";

export default function LegalListScreen() {
  const insets = useSafeAreaInsets();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const { data, isLoading, isError, refetch } = useConsents();
  useLocationConsentSync(data);
  const update = useUpdateConsent();

  const consentedAt = localDateLabel(data?.consentedAt ?? null);
  const termsVersion = data?.termsVersion ?? null;
  const agreedSub = [
    termsVersion ? `버전 ${termsVersion}` : null,
    consentedAt ? `${consentedAt} 동의` : null,
  ]
    .filter(Boolean)
    .join(" · ");

  const togglePhoto = (next: boolean) => {
    if (!data) return;
    update.mutate({
      locationConsent: data.locationConsent,
      photoConsent: next,
      termsVersion: data.termsVersion ?? TERMS_VERSION,
    });
  };

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <View style={styles.nav}>
        <Pressable style={styles.navBtn} onPress={() => router.back()} hitSlop={8}>
          <Icon name="chevron-left" size={23} />
        </Pressable>
        <Text style={styles.title}>약관·정책</Text>
      </View>

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scroll}>
        <ListGroup style={styles.firstGroup}>
          {LEGAL_DOCS.map((doc) => (
            <ListRow
              key={doc.slug}
              title={doc.title}
              chevron
              onPress={() => router.push(`/legal/${doc.slug}`)}
              testID={`legal-${doc.slug}`}
            />
          ))}
        </ListGroup>

        {isAuthenticated ? (
          <>
            <SectionTitle title="내 동의 내역" />
            {isLoading ? (
              <Text style={styles.note}>불러오는 중…</Text>
            ) : isError || !data ? (
              <View style={styles.errBox}>
                <Text style={styles.note}>동의 내역을 불러오지 못했어요</Text>
                <Pressable onPress={() => void refetch()} hitSlop={8}>
                  <Text style={styles.retry}>재시도</Text>
                </Pressable>
              </View>
            ) : (
              <ListGroup>
                <ListRow
                  icon="check"
                  title="[필수] 약관·개인정보 수집·이용"
                  sub={agreedSub.length > 0 ? agreedSub : "동의 기록 없음"}
                  testID="consent-terms"
                />
                <ListRow
                  icon="map-pin"
                  title="[선택] 위치정보 수집·이용"
                  sub="기기 설정에서 바꿀 수 있어요"
                  value={data.locationConsent ? "허용" : "거부"}
                  tone={data.locationConsent ? "on" : "off"}
                  chevron
                  onPress={() => void Linking.openSettings()}
                  testID="consent-location"
                />
                <ListRow
                  icon="photo"
                  title="[선택] 사진 분석 이용"
                  sub={data.photoConsent ? "동의함 · 언제든 철회할 수 있어요" : "동의하지 않음"}
                  right={
                    <Switch
                      value={data.photoConsent}
                      onValueChange={togglePhoto}
                      trackColor={{ false: colors.line, true: colors.accent }}
                      testID="consent-photo-switch"
                    />
                  }
                />
              </ListGroup>
            )}
          </>
        ) : null}
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
  note: { paddingHorizontal: spacing.lg, fontSize: 13, color: colors.ter },
  errBox: { flexDirection: "row", alignItems: "center", gap: spacing.md, paddingRight: spacing.lg },
  retry: { fontSize: 13, fontWeight: "700", color: colors.ink },
});
