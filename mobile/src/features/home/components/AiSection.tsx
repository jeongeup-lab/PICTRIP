import { Pressable, StyleSheet, Text, View } from "react-native";
import { router } from "expo-router";
import { Icon } from "@/components/Icon";
import { GridSkeleton } from "@/features/home/components/RankSection";
import { SectionHead } from "@/features/home/components/SectionHead";
import { SpotGrid } from "@/features/home/components/SpotGrid";
import { anchorBadge, categorySubtitle } from "@/features/home/lib/card-subtitle";
import type { Recommendations } from "@/features/home/api";
import { useAuthGate } from "@/features/auth/hooks/use-auth-gate";
import { colors, spacing } from "@/constants/theme";

interface Props {
  displayName: string | null;
  data: Recommendations | undefined;
  isLoading: boolean;
}

export function AiSection({ displayName, data, isLoading }: Props) {
  const requireAuth = useAuthGate();
  const ready = data?.ready === true && data.items.length > 0;

  const openPicker = () => {
    void (async () => {
      if (await requireAuth("save")) router.push("/taste");
    })();
  };

  return (
    <View style={styles.section}>
      <SectionHead
        title="님을 위한 AI 추천 장소"
        highlight={displayName ?? "여행자"}
        caption={
          ready
            ? "저장한 장소와 닮은 곳을 골랐어요."
            : "마음에 드는 장소를 저장하면 취향에 맞춰 추천해 드려요."
        }
      />
      {isLoading ? (
        <GridSkeleton />
      ) : ready ? (
        <SpotGrid cards={data.items} subtitleOf={categorySubtitle} badgeOf={anchorBadge} />
      ) : (
        <EmptyState remaining={remainingSaves(data)} onPress={openPicker} />
      )}
    </View>
  );
}

function remainingSaves(data: Recommendations | undefined): number | null {
  if (!data) return null;
  return Math.max(0, data.minSaved - data.savedCount);
}

function EmptyState({ remaining, onPress }: { remaining: number | null; onPress: () => void }) {
  return (
    <Pressable testID="home-taste-cta" onPress={onPress} style={styles.empty}>
      <View style={styles.emptyIcon}>
        <Icon name="sparkle" size={26} color={colors.accentText} />
      </View>
      <Text style={styles.emptyTitle}>취향 카드로 시작하기</Text>
      <Text style={styles.emptyBody}>
        {remaining && remaining > 0
          ? `${remaining}곳만 더 저장하면 추천이 시작돼요.`
          : "카드를 넘기며 마음에 드는 곳만 저장해 주세요."}
      </Text>
      <View style={styles.emptyCta}>
        <Text style={styles.emptyCtaText}>카드 고르러 가기</Text>
        <Icon name="chevron-right" size={16} color={colors.onImage} />
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  section: { paddingTop: spacing.sm },
  empty: {
    marginHorizontal: spacing.lg,
    padding: spacing.lg,
    borderRadius: 18,
    alignItems: "center",
    gap: 8,
    backgroundColor: colors.inset,
    borderWidth: 1,
    borderColor: colors.line,
  },
  emptyIcon: {
    width: 56,
    height: 56,
    borderRadius: 28,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.accentFill,
    marginBottom: 2,
  },
  emptyTitle: { fontSize: 16, fontWeight: "800", letterSpacing: -0.3, color: colors.ink },
  emptyBody: { fontSize: 13.5, lineHeight: 20, color: colors.sec, textAlign: "center" },
  emptyCta: {
    marginTop: 6,
    flexDirection: "row",
    alignItems: "center",
    gap: 2,
    paddingHorizontal: 18,
    height: 44,
    borderRadius: 12,
    backgroundColor: colors.accent,
  },
  emptyCtaText: { fontSize: 15, fontWeight: "700", color: colors.onImage },
});
