import { useRef, useState } from "react";
import { View, Text, Pressable, ScrollView, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router } from "expo-router";
import { Icon } from "@/components/Icon";
import { Skeleton } from "@/components/Skeleton";
import { Toast, TOAST_UNDO_MS } from "@/components/Toast";
import { InfoBox } from "@/components/InfoBox";
import { ListGroup } from "@/components/ListGroup";
import { SectionTitle } from "@/components/SectionTitle";
import { PrimaryButton } from "@/components/PrimaryButton";
import { SavedCard } from "@/features/saved/components/SavedCard";
import { RecentSpotRow } from "@/features/saved/components/RecentSpotRow";
import { useSavedList, useSaveMutation, useUnsaveMutation } from "@/features/saved/queries";
import { unsaveMessage } from "@/features/saved/lib/undo-message";
import { useRecentSpots } from "@/features/spots/stores/recent-store";
import { prefetchSpot } from "@/features/spots/queries";
import type { SpotCard } from "@/lib/api-types";
import { colors, spacing, radii } from "@/constants/theme";

export const EMPTY_HEADLINE = "아직 스크랩한 곳이 없어요";

export const UNSAVE_FAILED = "스크랩 해제를 못 했어요. 잠시 뒤 다시 시도해 주세요";

export const RESAVE_FAILED = "되돌리지 못했어요. 다시 스크랩해 주세요";

interface Notice {
  message: string;
  undoContentId: string | null;
}

export default function SavedScreen() {
  const insets = useSafeAreaInsets();
  const { data, isLoading } = useSavedList();
  const unsave = useUnsaveMutation();
  const resave = useSaveMutation();
  const recents = useRecentSpots((s) => s.spots);
  const [notice, setNotice] = useState<Notice | null>(null);
  const unsaving = useRef<Promise<boolean> | null>(null);

  const list = data ?? [];

  const openSpot = (spot: SpotCard) => {
    prefetchSpot(spot);
    router.push(`/spots/${spot.contentId}`);
  };

  const remove = (spot: SpotCard) => {
    setNotice({ message: unsaveMessage(spot.title), undoContentId: spot.contentId });
    unsaving.current = unsave.mutateAsync(spot.contentId).then(
      () => true,
      () => {
        setNotice((current) =>
          current === null || current.undoContentId === spot.contentId
            ? { message: UNSAVE_FAILED, undoContentId: null }
            : current,
        );
        return false;
      },
    );
  };

  const undo = () => {
    const contentId = notice?.undoContentId;
    if (!contentId) return;
    const settled = unsaving.current ?? Promise.resolve(true);
    setNotice(null);
    void settled.then((removed) => {
      if (!removed) return;
      resave.mutate(contentId, {
        onError: () =>
          setNotice((current) =>
            current === null ? { message: RESAVE_FAILED, undoContentId: null } : current,
          ),
      });
    });
  };

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <View style={styles.nav}>
        <Pressable style={styles.navBtn} onPress={() => router.back()} hitSlop={8}>
          <Icon name="chevron-left" size={23} />
        </Pressable>
        <Text style={styles.title}>스크랩{list.length > 0 ? ` ${list.length}` : ""}</Text>
      </View>

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scroll}>
        {isLoading ? (
          <View style={styles.loading}>
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} height={74} radius={radii.md} />
            ))}
          </View>
        ) : list.length === 0 ? (
          <EmptyState recents={recents} onOpenSpot={openSpot} />
        ) : (
          <View style={styles.album}>
            {list.map((spot) => (
              <SavedCard
                key={spot.contentId}
                spot={spot}
                onPressIn={() => prefetchSpot(spot)}
                onPress={() => openSpot(spot)}
                onUnsave={() => remove(spot)}
                testID={`saved-${spot.contentId}`}
              />
            ))}
          </View>
        )}
      </ScrollView>

      <Toast
        message={notice?.message ?? null}
        bottom={insets.bottom + spacing.lg}
        onHide={() => setNotice(null)}
        action={notice?.undoContentId ? { label: "되돌리기", onPress: undo } : null}
        durationMs={TOAST_UNDO_MS}
        testID="unsave-toast"
      />
    </View>
  );
}

function EmptyState({
  recents,
  onOpenSpot,
}: {
  recents: SpotCard[];
  onOpenSpot: (spot: SpotCard) => void;
}) {
  return (
    <View>
      <View style={styles.emptyHead}>
        <View style={styles.emptyIcon}>
          <Icon name="bookmark" size={28} color={colors.accent} strokeWidth={1.7} />
        </View>
        <Text style={styles.emptyTitle}>{EMPTY_HEADLINE}</Text>
        <Text style={styles.emptySub}>카드의 스크랩 버튼을 누르면 여기 모여요.</Text>
      </View>

      <InfoBox
        title="이렇게 쓰면 편해요"
        text="여행 탭에서 결과를 받고 마음에 드는 곳만 스크랩 → 스크랩에 앨범처럼 모아두고 다음 여행을 짜는 흐름이에요."
      >
        <View style={styles.emptyAction}>
          <PrimaryButton
            label="여행 탭 열기"
            onPress={() => router.push("/(tabs)/travel")}
            testID="open-travel"
          />
        </View>
      </InfoBox>

      {recents.length > 0 ? (
        <>
          <SectionTitle title="최근 본 곳" />
          <ListGroup>
            {recents.map((spot) => (
              <RecentSpotRow
                key={spot.contentId}
                spot={spot}
                onPress={() => onOpenSpot(spot)}
                testID={`recent-${spot.contentId}`}
              />
            ))}
          </ListGroup>
        </>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  nav: { height: 50, flexDirection: "row", alignItems: "center" },
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
  loading: { gap: 10, paddingHorizontal: spacing.md, paddingTop: spacing.sm },
  album: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "space-between",
    rowGap: 18,
    paddingHorizontal: spacing.md,
    paddingTop: spacing.sm,
  },
  emptyHead: { alignItems: "center", paddingHorizontal: spacing.xl, paddingTop: 40 },
  emptyIcon: {
    width: 68,
    height: 68,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.raise,
    alignItems: "center",
    justifyContent: "center",
  },
  emptyTitle: {
    marginTop: 18,
    fontSize: 18,
    fontWeight: "800",
    letterSpacing: -0.4,
    color: colors.ink,
  },
  emptySub: { marginTop: 8, fontSize: 13, color: colors.sec, textAlign: "center" },
  emptyAction: { marginTop: spacing.md },
});
