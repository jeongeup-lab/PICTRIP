import { StyleSheet, Text, View } from "react-native";
import { router } from "expo-router";
import { Icon } from "@/components/Icon";
import { PrimaryButton } from "@/components/PrimaryButton";
import { GridSkeleton } from "@/features/home/components/RankSection";
import { SectionHead } from "@/features/home/components/SectionHead";
import { SpotGrid } from "@/features/home/components/SpotGrid";
import { categorySubtitle } from "@/features/home/lib/card-subtitle";
import type { Recommendations } from "@/features/home/api";
import { useAuthGate } from "@/features/auth/hooks/use-auth-gate";
import { colors, radii, spacing } from "@/constants/theme";

interface Props {
  displayName: string | null;
  data: Recommendations | undefined;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
}

export function AiSection({ displayName, data, isLoading, isError, onRetry }: Props) {
  const requireAuth = useAuthGate();
  const ready = data?.ready === true && data.items.length > 0;

  const openPicker = () => {
    void (async () => {
      if (await requireAuth("save")) router.push("/taste");
    })();
  };

  return (
    <View style={styles.section}>
      <SectionHead title="님을 위한 AI 추천 장소" highlight={displayName ?? "여행자"} />
      {isLoading ? (
        <GridSkeleton />
      ) : isError ? (
        <View testID="home-ai-error" style={styles.error}>
          <Text style={styles.errorText}>추천을 불러오지 못했어요.</Text>
          <PrimaryButton testID="home-ai-retry" label="다시 시도" onPress={onRetry} />
        </View>
      ) : ready ? (
        <SpotGrid cards={data.items} subtitleOf={categorySubtitle} />
      ) : (
        <EmptyState onPress={openPicker} />
      )}
    </View>
  );
}

function EmptyState({ onPress }: { onPress: () => void }) {
  return (
    <View style={styles.empty}>
      <View style={styles.emptyIcon}>
        <Icon name="sparkle" size={26} color={colors.accentText} />
      </View>
      <Text style={styles.emptyTitle}>취향 카드로 시작하기</Text>
      <Text style={styles.emptyDescription}>마음에 드는 곳을 고르면 맞춤 추천을 준비해요.</Text>
      <View style={styles.emptyAction}>
        <PrimaryButton testID="home-taste-cta" label="카드 고르러 가기" onPress={onPress} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  section: { paddingTop: spacing.sm },
  empty: {
    marginHorizontal: spacing.lg,
    padding: spacing.lg,
    borderRadius: radii.lg,
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: colors.inset,
    borderWidth: 1,
    borderColor: colors.line,
  },
  emptyIcon: {
    width: spacing.xxl + spacing.xl,
    height: spacing.xxl + spacing.xl,
    borderRadius: radii.pill,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.accentFill,
    marginBottom: spacing.xs,
  },
  emptyTitle: { fontSize: 16, fontWeight: "800", letterSpacing: -0.3, color: colors.ink },
  emptyDescription: { fontSize: 14, fontWeight: "500", color: colors.sec, textAlign: "center" },
  emptyAction: { alignSelf: "stretch", marginTop: spacing.xs },
  error: { alignItems: "center", gap: spacing.md, paddingHorizontal: spacing.lg },
  errorText: { fontSize: 14, color: colors.sec },
});
