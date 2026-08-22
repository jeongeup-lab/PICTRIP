import { View, Text, Pressable, ScrollView, Switch, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router } from "expo-router";
import { ScreenHeader } from "@/components/ScreenHeader";
import { InfoBox } from "@/components/InfoBox";
import { ListGroup } from "@/components/ListGroup";
import { ListRow } from "@/components/ListRow";
import { PrimaryButton } from "@/components/PrimaryButton";
import { useAuthStore } from "@/features/auth/stores/auth-store";
import { useConsents } from "@/features/consent/queries";
import { useLocationConsentSync } from "@/features/consent/hooks/use-location-consent-sync";
import { useAiTransferConsent } from "@/features/consent/hooks/use-ai-transfer-consent";
import { AI_TRANSFER } from "@/features/consent/lib/ai-transfer";
import { colors, spacing } from "@/constants/theme";

export default function ConsentScreen() {
  const insets = useSafeAreaInsets();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const { data, isLoading, isError, refetch } = useConsents();
  const { granted: aiGranted, decide: decideAi } = useAiTransferConsent();
  useLocationConsentSync(data);

  const aiRow = (
    <ListGroup style={styles.group}>
      <ListRow
        title={AI_TRANSFER.rowTitle}
        titleLines={2}
        sub={AI_TRANSFER.rowSub}
        value={aiGranted ? AI_TRANSFER.rowOn : AI_TRANSFER.rowOff}
        tone={aiGranted ? "on" : "off"}
        right={
          <Switch
            testID="consent-ai-switch"
            accessibilityLabel={AI_TRANSFER.rowTitle}
            value={aiGranted}
            onValueChange={(next) => void decideAi(next)}
            trackColor={{ false: colors.fillStrong, true: colors.accent }}
          />
        }
        testID="consent-ai"
      />
    </ListGroup>
  );
  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <ScreenHeader title="동의 내역" fallback="/(tabs)/profile" />

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scroll}>
        {!isAuthenticated ? (
          <InfoBox
            title="로그인이 필요해요"
            text="약관·위치 동의 내역은 로그인한 계정에서만 볼 수 있어요."
            testID="consent-guest"
          >
            <View style={styles.guest}>
              <PrimaryButton label="로그인하기" onPress={() => router.push("/auth/login")} />
            </View>
          </InfoBox>
        ) : isLoading ? (
          <Text style={styles.note}>불러오는 중…</Text>
        ) : isError || !data ? (
          <View style={styles.errBox}>
            <Text style={styles.note}>동의 정보를 불러오지 못했어요</Text>
            <Pressable onPress={() => void refetch()} hitSlop={8}>
              <Text style={styles.retry}>재시도</Text>
            </Pressable>
          </View>
        ) : (
          <ListGroup style={styles.group}>
            <ListRow
              title="[필수] 약관·개인정보 수집·이용"
              titleLines={2}
              value={data.termsVersion ? "동의함" : "기록 없음"}
              tone={data.termsVersion ? "on" : "off"}
              testID="consent-terms"
            />
            <ListRow
              title="[선택] 위치정보 수집·이용"
              titleLines={2}
              value={data.locationConsent ? "동의함" : "동의 안 함"}
              tone={data.locationConsent ? "on" : "off"}
              testID="consent-location"
            />
          </ListGroup>
        )}

        {aiRow}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  scroll: { paddingBottom: spacing.xxl },
  group: { marginTop: spacing.md },
  note: { textAlign: "center", color: colors.ter, fontSize: 14, marginTop: spacing.xxl },
  errBox: { alignItems: "center", gap: spacing.md, marginTop: spacing.xxl },
  retry: { color: colors.ink, fontSize: 14, fontWeight: "700" },
  guest: { marginTop: spacing.md },
});
