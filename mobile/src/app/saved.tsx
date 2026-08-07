import { useMemo, useRef, useState } from "react";
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
import { SavedListRow } from "@/features/saved/components/SavedListRow";
import { SwipeRow } from "@/features/saved/components/SwipeRow";
import { RecentSpotRow } from "@/features/saved/components/RecentSpotRow";
import { useSavedList, useSaveMutation, useUnsaveMutation } from "@/features/saved/queries";
import {
  SAVED_SORTS,
  distanceLabel,
  distanceMeters,
  sortSaved,
  type SavedSort,
} from "@/features/saved/lib/sort";
import { unsaveMessage } from "@/features/saved/lib/undo-message";
import { useRecentSpots } from "@/features/spots/stores/recent-store";
import { prefetchSpot } from "@/features/spots/queries";
import { useNearbyCoords } from "@/features/travel/hooks/use-nearby-coords";
import type { SpotCard } from "@/lib/api-types";
import { colors, spacing, radii } from "@/constants/theme";

export const EMPTY_HEADLINE = "아직 스크랩한 곳이 없어요";

interface Removed {
  message: string;
  contentId: string;
}

export default function SavedScreen() {
  const insets = useSafeAreaInsets();
  const { data, isLoading } = useSavedList();
  const unsave = useUnsaveMutation();
  const resave = useSaveMutation();
  const recents = useRecentSpots((s) => s.spots);
  const { coords, askable, ask } = useNearbyCoords();
  const [sort, setSort] = useState<SavedSort>("recent");
  const [grid, setGrid] = useState(false);
  const [removed, setRemoved] = useState<Removed | null>(null);
  const unsaving = useRef<Promise<unknown> | null>(null);

  const list = useMemo(() => sortSaved(data ?? [], sort, coords), [data, sort, coords]);

  const pickSort = (mode: SavedSort) => {
    setSort(mode);
    if (mode === "near" && !coords && askable) void ask();
  };

  const openSpot = (spot: SpotCard) => {
    prefetchSpot(spot);
    router.push(`/spots/${spot.contentId}`);
  };

  const remove = (spot: SpotCard) => {
    unsaving.current = unsave.mutateAsync(spot.contentId).catch(() => undefined);
    setRemoved({ message: unsaveMessage(spot.title), contentId: spot.contentId });
  };

  const undo = () => {
    if (!removed) return;
    const { contentId } = removed;
    const settled = unsaving.current ?? Promise.resolve();
    setRemoved(null);
    void settled.then(() => resave.mutate(contentId));
  };

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <View style={styles.nav}>
        <Pressable style={styles.navBtn} onPress={() => router.back()} hitSlop={8}>
          <Icon name="chevron-left" size={23} />
        </Pressable>
        <Text style={styles.title}>스크랩{list.length > 0 ? ` ${list.length}` : ""}</Text>
        {list.length > 0 ? (
          <Pressable
            accessibilityRole="button"
            style={styles.navBtn}
            hitSlop={8}
            onPress={() => setGrid((g) => !g)}
            testID="toggle-view"
          >
            <Icon name={grid ? "sort" : "grid"} size={19} color={colors.ink} />
          </Pressable>
        ) : null}
      </View>

      {list.length > 0 ? (
        <View style={styles.chips}>
          {SAVED_SORTS.map((option) => (
            <Pressable
              key={option.mode}
              accessibilityRole="button"
              style={[styles.chip, sort === option.mode && styles.chipOn]}
              onPress={() => pickSort(option.mode)}
              testID={`sort-${option.mode}`}
            >
              <Text style={[styles.chipText, sort === option.mode && styles.chipTextOn]}>
                {option.label}
              </Text>
            </Pressable>
          ))}
        </View>
      ) : null}

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={grid ? styles.gridPad : styles.listPad}
      >
        {isLoading ? (
          <View style={styles.loading}>
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} height={74} radius={radii.md} />
            ))}
          </View>
        ) : list.length === 0 ? (
          <EmptyState recents={recents} onOpenSpot={openSpot} />
        ) : grid ? (
          <View style={styles.grid}>
            {list.map((spot) => (
              <SavedCard
                key={spot.contentId}
                spot={spot}
                onPressIn={() => prefetchSpot(spot)}
                onPress={() => openSpot(spot)}
                onUnsave={() => remove(spot)}
              />
            ))}
          </View>
        ) : (
          list.map((spot) => (
            <SwipeRow
              key={spot.contentId}
              actionLabel="해제"
              onAction={() => remove(spot)}
              testID={`swipe-${spot.contentId}`}
            >
              <SavedListRow
                spot={spot}
                distance={coords ? distanceLabel(distanceMeters(spot, coords)) : null}
                onPressIn={() => prefetchSpot(spot)}
                onPress={() => openSpot(spot)}
                testID={`saved-${spot.contentId}`}
              />
            </SwipeRow>
          ))
        )}
      </ScrollView>

      <Toast
        message={removed?.message ?? null}
        bottom={insets.bottom + spacing.lg}
        onHide={() => setRemoved(null)}
        action={{ label: "되돌리기", onPress: undo }}
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
          <Icon name="heart" size={28} color={colors.accent} strokeWidth={1.7} />
        </View>
        <Text style={styles.emptyTitle}>{EMPTY_HEADLINE}</Text>
        <Text style={styles.emptySub}>카드의 하트를 누르면 여기 모여요.</Text>
      </View>

      <InfoBox
        title="이렇게 쓰면 편해요"
        text="여행 탭에서 결과를 받고 마음에 드는 곳만 하트 → 스크랩에서 가까운 순으로 정렬해 동선을 짜는 흐름이에요."
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
  nav: { height: 50, flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
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
  chips: { flexDirection: "row", gap: 7, paddingHorizontal: spacing.md, paddingBottom: 10 },
  chip: {
    height: 32,
    paddingHorizontal: 13,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.raise,
    alignItems: "center",
    justifyContent: "center",
  },
  chipOn: { backgroundColor: colors.ink, borderColor: colors.ink },
  chipText: { fontSize: 12.5, fontWeight: "700", color: colors.sec },
  chipTextOn: { color: colors.bg },
  listPad: { paddingBottom: spacing.xxl },
  gridPad: { paddingBottom: spacing.xxl },
  loading: { gap: 10, paddingHorizontal: spacing.md, paddingTop: spacing.sm },
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "space-between",
    rowGap: 12,
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
