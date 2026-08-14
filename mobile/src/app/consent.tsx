import { View, Text, Pressable, ScrollView, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router } from "expo-router";
import { ScreenHeader } from "@/components/ScreenHeader";
import { InfoBox } from "@/components/InfoBox";
import { PrimaryButton } from "@/components/PrimaryButton";
import { useAuthStore } from "@/features/auth/stores/auth-store";
import { useConsents } from "@/features/consent/queries";
import { useLocationConsentSync } from "@/features/consent/hooks/use-location-consent-sync";
import { colors, spacing } from "@/constants/theme";

export default function ConsentScreen() {
  const insets = useSafeAreaInsets();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const { data, isLoading, isError, refetch } = useConsents();
  useLocationConsentSync(data);
  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <ScreenHeader title="동의 내역" fallback="/(tabs)/profile" />

      {!isAuthenticated ? (
        <InfoBox
          title="로그인이 필요해요"
          text="동의 내역은 로그인한 계정에서만 볼 수 있어요."
          testID="consent-guest"
        >
          <View style={styles.guest}>
            <PrimaryButton label="로그인하기" onPress={() => router.push("/auth/login")} />
          </View>
        </InfoBox>
      ) : (
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
                  <Text style={styles.label}>[필수] 약관·개인정보 수집·이용</Text>
                  <Text style={[styles.value, data.termsVersion && styles.valueOn]}>
                    {data.termsVersion ? "동의함" : "기록 없음"}
                  </Text>
                </View>
                <View style={styles.divider} />
                <View style={styles.row}>
                  <Text style={styles.label}>[선택] 위치정보 수집·이용</Text>
                  <Text style={[styles.value, data.locationConsent && styles.valueOn]}>
                    {data.locationConsent ? "동의함" : "동의 안 함"}
                  </Text>
                </View>
              </View>
            </>
          )}
        </ScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.inset },
  group: { backgroundColor: colors.bg, marginTop: 9 },
  row: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.md,
    paddingVertical: 16,
    paddingHorizontal: spacing.lg,
  },
  label: { flex: 1, fontSize: 15.5, fontWeight: "600", color: colors.ink },
  value: { fontSize: 14, color: colors.ter },
  valueOn: { color: colors.accentText, fontWeight: "700" },
  divider: { height: 1, marginLeft: spacing.lg, backgroundColor: colors.line },
  note: { textAlign: "center", color: colors.ter, fontSize: 14, marginTop: spacing.xxl },
  errBox: { alignItems: "center", gap: spacing.md, marginTop: spacing.xxl },
  retry: { color: colors.ink, fontSize: 14, fontWeight: "700" },
  guest: { marginTop: spacing.md },
});
