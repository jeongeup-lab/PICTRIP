import { StyleSheet, Text, View } from "react-native";
import { PrimaryButton } from "@/components/PrimaryButton";
import { SectionHead } from "@/features/home/components/SectionHead";
import { GridSkeleton, SpotGrid } from "@/features/home/components/SpotGrid";
import { categorySubtitle } from "@/features/home/lib/card-subtitle";
import type { HomeSpotCard, Recommendations } from "@/features/home/api";
import { colors, spacing } from "@/constants/theme";

export const AI_KICKER = "FOR YOU";
export const AI_GRID_SIZE = 4;
export const FALLBACK_CAPTION = "아직 취향을 몰라 무작위로 골랐어요";

export function tasteCaption(savedCount: number): string {
  return `스크랩 ${savedCount}곳에서 읽은 취향`;
}

interface Props {
  displayName: string | null;
  data: Recommendations | undefined;
  fallbackCards: HomeSpotCard[];
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
}

export function AiSection({
  displayName,
  data,
  fallbackCards,
  isLoading,
  isError,
  onRetry,
}: Props) {
  const ready = data?.ready === true && data.items.length > 0;
  const cards = ready ? data.items : fallbackCards;

  return (
    <View style={styles.section}>
      <SectionHead
        kicker={AI_KICKER}
        title="님을 위한 AI 추천 장소"
        highlight={displayName ?? "여행자"}
        caption={ready ? tasteCaption(data.savedCount) : FALLBACK_CAPTION}
      />
      {isLoading ? (
        <GridSkeleton />
      ) : isError ? (
        <View testID="home-ai-error" style={styles.error}>
          <Text style={styles.errorText}>추천을 불러오지 못했어요.</Text>
          <PrimaryButton testID="home-ai-retry" label="다시 시도" onPress={onRetry} />
        </View>
      ) : (
        <SpotGrid cards={cards.slice(0, AI_GRID_SIZE)} subtitleOf={categorySubtitle} />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  section: { paddingTop: spacing.sm },
  error: { alignItems: "center", gap: spacing.md, paddingHorizontal: spacing.lg },
  errorText: { fontSize: 14, color: colors.sec },
});
