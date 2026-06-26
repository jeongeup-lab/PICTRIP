import { useCallback, useEffect, useMemo, useState } from "react";
import { Animated, View, Text, Pressable, ScrollView, StyleSheet, Dimensions } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router } from "expo-router";
import { Icon } from "@/components/Icon";
import { Skeleton } from "@/components/Skeleton";
import { KakaoWebMap } from "@/features/map/components/KakaoWebMap";
import { MapBottomSheet, SHEET_SNAP_Y } from "@/features/map/components/MapBottomSheet";
import { CategoryChips } from "@/features/map/components/CategoryChips";
import { NearbyCard } from "@/features/map/components/NearbyCard";
import { SearchHerePill } from "@/features/map/components/SearchHerePill";
import { RecenterFab } from "@/features/map/components/RecenterFab";
import { PermissionPrimer } from "@/features/map/components/PermissionPrimer";
import { RegionPicker } from "@/features/map/components/RegionPicker";
import { useMapStore } from "@/features/map/stores/map-store";
import { useMapInit } from "@/features/map/hooks/use-map-init";
import { useNearbyMap, useRegionLabel } from "@/features/map/queries";
import { prefetchSpot } from "@/features/spots/queries";
import { formatHeaderLabel } from "@/features/map/lib/region-label";
import { NEARBY_CAP } from "@/constants/map";
import { colors, spacing } from "@/constants/theme";

export default function MapTab() {
  const insets = useSafeAreaInsets();
  const s = useMapStore();
  const { perm, allow, skipToSeoul, recenter } = useMapInit();
  const [pickerOpen, setPickerOpen] = useState(false);

  const nearby = useNearbyMap(s.center, s.category);
  const label = useRegionLabel(s.center, s.anchorSource !== "region");
  const spots = (nearby.data ?? []).slice(0, NEARBY_CAP);

  // The sheet owns its translateY Animated.Value and hands it up via onTranslate.
  // We start from a fallback matching the current snap so the pill/FAB are placed
  // correctly on the very first frame (before the sheet's mount effect fires).
  const [sheetY, setSheetY] = useState<Animated.Value>(
    () => new Animated.Value(SHEET_SNAP_Y[s.snap]),
  );
  const handleTranslate = useCallback((v: Animated.Value) => setSheetY(v), []);
  // Anchor each control so its BOTTOM edge sits SHEET_GAP px above the sheet top.
  // Derived from the sheet's translateY; the sheet JS-drives that value (see
  // MapBottomSheet) so these followers update every frame during drag AND snap.
  const pillTranslateY = useMemo(
    () => Animated.subtract(sheetY, SHEET_GAP + PILL_HEIGHT),
    [sheetY],
  );
  const fabTranslateY = useMemo(() => Animated.subtract(sheetY, SHEET_GAP + FAB_HEIGHT), [sheetY]);

  // Last list card must clear the off-screen sheet overflow + tab bar + inset.
  // useBottomTabBarHeight isn't publicly exported by expo-router (and
  // @react-navigation/bottom-tabs isn't installed), so use the iOS default tab
  // content height (49) + safe-area inset, per the plan's documented fallback.
  const tabBarHeight = TAB_BAR_CONTENT_HEIGHT + insets.bottom;
  const listPaddingBottom = tabBarHeight + insets.bottom + WINDOW_H * 0.1 + spacing.xxl;

  useEffect(() => {
    if (label.data) s.setLabel(label.data);
  }, [label.data]); // eslint-disable-line react-hooks/exhaustive-deps

  if (perm === "undetermined" || perm === "denied") {
    return (
      <PermissionPrimer
        variant={perm === "denied" ? "denied" : "priming"}
        onAllow={allow}
        onSkip={skipToSeoul}
      />
    );
  }

  return (
    <View style={styles.root}>
      <KakaoWebMap
        center={s.center}
        pins={spots}
        userLocation={s.gpsCoords}
        onPinTap={(id) => {
          s.selectSpot(id);
          s.setSnap("half");
        }}
        onCenterChanged={(c) => s.onViewportChange(c)}
      />

      <View style={[styles.header, { top: insets.top + spacing.xs }]}>
        <Pressable style={styles.label} onPress={() => setPickerOpen(true)}>
          <Text numberOfLines={1} style={styles.labelText}>
            {formatHeaderLabel(s.anchorSource, s.label)}
          </Text>
          <Icon name="chevron-down" size={18} color={colors.ink} />
        </Pressable>
      </View>

      {s.pillVisible() ? (
        <Animated.View
          style={[styles.pill, { transform: [{ translateY: pillTranslateY }] }]}
          pointerEvents="box-none"
        >
          <SearchHerePill onPress={() => s.searchHere()} />
        </Animated.View>
      ) : null}
      <Animated.View
        style={[styles.fab, { transform: [{ translateY: fabTranslateY }] }]}
        pointerEvents="box-none"
      >
        <RecenterFab onPress={recenter} />
      </Animated.View>

      <MapBottomSheet
        snap={s.snap}
        onSnapChange={s.setSnap}
        onTranslate={handleTranslate}
        headerExtra={<CategoryChips value={s.category} onChange={s.setCategory} />}
      >
        {nearby.isLoading ? (
          <View style={[styles.list, { paddingBottom: listPaddingBottom }]}>
            {[0, 1, 2].map((i) => (
              <Skeleton
                key={i}
                height={92}
                style={{ marginHorizontal: spacing.lg, marginBottom: spacing.sm }}
                radius={14}
              />
            ))}
          </View>
        ) : nearby.isError ? (
          <View style={[styles.center, { paddingBottom: listPaddingBottom }]}>
            <Text style={styles.dim}>주변 정보를 불러오지 못했어요</Text>
            <Pressable style={styles.retry} onPress={() => nearby.refetch()}>
              <Text style={styles.retryText}>다시 시도</Text>
            </Pressable>
          </View>
        ) : spots.length === 0 ? (
          <View style={[styles.center, { paddingBottom: listPaddingBottom }]}>
            <Text style={styles.dim}>이 주변엔 아직 추천 스팟이 없어요</Text>
            <Text style={styles.dimSub}>
              지도를 옮겨 &apos;이 지역에서 검색&apos;을 누르거나, 다른 지역을 선택해 보세요
            </Text>
          </View>
        ) : (
          <ScrollView
            showsVerticalScrollIndicator={false}
            contentContainerStyle={{ paddingBottom: listPaddingBottom }}
          >
            {spots.map((spot) => (
              <NearbyCard
                key={spot.contentId}
                spot={spot}
                selected={spot.contentId === s.selectedSpotId}
                onPressIn={() => prefetchSpot(spot.contentId)}
                onPress={() => router.push(`/spots/${spot.contentId}`)}
              />
            ))}
          </ScrollView>
        )}
      </MapBottomSheet>

      <RegionPicker
        visible={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onApply={(centroid, name) => {
          s.applyRegion(centroid);
          s.setLabel({ sido: null, sigungu: null, dong: null, label: name });
          setPickerOpen(false);
        }}
      />
    </View>
  );
}

const WINDOW_H = Dimensions.get("window").height;
// RN bottom-tab content height on iOS (excludes the safe-area inset, added separately).
const TAB_BAR_CONTENT_HEIGHT = 49;
const PILL_HEIGHT = 38; // SearchHerePill height
const FAB_HEIGHT = 46; // RecenterFab height
const SHEET_GAP = 14; // mockup: control bottom sits 14px above the sheet top edge

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  header: { position: "absolute", left: spacing.lg, right: spacing.lg },
  label: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    alignSelf: "flex-start",
    height: 40,
    paddingHorizontal: 16,
    borderRadius: 20,
    backgroundColor: colors.bg,
    shadowColor: "#100E12",
    shadowOpacity: 0.12,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 2 },
    elevation: 4,
    maxWidth: "80%",
  },
  labelText: { fontSize: 15, fontWeight: "700", color: colors.ink },
  // top:0 + translateY anchors these to the sheet's animated top edge (see body).
  pill: { position: "absolute", left: 0, right: 0, top: 0, alignItems: "center" },
  fab: { position: "absolute", right: spacing.lg, top: 0 },
  list: { paddingTop: spacing.sm },
  center: {
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: spacing.xxl,
    paddingHorizontal: spacing.xl,
    gap: spacing.sm,
  },
  dim: { color: colors.sec, fontSize: 15, fontWeight: "600", textAlign: "center" },
  dimSub: { color: colors.ter, fontSize: 13, textAlign: "center", lineHeight: 19 },
  retry: {
    marginTop: spacing.xs,
    paddingHorizontal: 18,
    height: 38,
    borderRadius: 999,
    backgroundColor: colors.fill,
    alignItems: "center",
    justifyContent: "center",
  },
  retryText: { fontSize: 13.5, fontWeight: "700", color: colors.ink },
});
