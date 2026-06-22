import { useEffect, useRef, useState } from "react";
import { View, Text, Pressable, ScrollView, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router } from "expo-router";
import { Icon } from "@/components/Icon";
import { Skeleton } from "@/components/Skeleton";
import { KakaoWebMap } from "@/features/map/components/KakaoWebMap";
import { MapBottomSheet } from "@/features/map/components/MapBottomSheet";
import { CategoryChips } from "@/features/map/components/CategoryChips";
import { NearbyCard } from "@/features/map/components/NearbyCard";
import { SearchHerePill } from "@/features/map/components/SearchHerePill";
import { RecenterFab } from "@/features/map/components/RecenterFab";
import { PermissionPrimer } from "@/features/map/components/PermissionPrimer";
import { RegionPicker } from "@/features/map/components/RegionPicker";
import { useMapStore } from "@/features/map/stores/map-store";
import { useNearbyMap, useRegionLabel } from "@/features/map/queries";
import { formatHeaderLabel } from "@/features/map/lib/region-label";
import {
  getPermissionStatus,
  requestPermission,
  getCurrentCoords,
  type PermStatus,
} from "@/features/map/usecases/request-location";
import { SEOUL_CITY_HALL, NEARBY_CAP } from "@/constants/map";
import { colors, spacing } from "@/constants/theme";

export default function MapTab() {
  const insets = useSafeAreaInsets();
  const s = useMapStore();
  const [perm, setPerm] = useState<PermStatus | "ready">("undetermined");
  const [pickerOpen, setPickerOpen] = useState(false);
  const started = useRef(false);

  const nearby = useNearbyMap(s.center, s.category);
  const label = useRegionLabel(s.center, s.anchorSource !== "region");
  const spots = (nearby.data ?? []).slice(0, NEARBY_CAP);

  useEffect(() => {
    if (label.data) s.setLabel(label.data);
  }, [label.data]); // eslint-disable-line react-hooks/exhaustive-deps

  // Entry: branch on permission status (S05 §1.4).
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    (async () => {
      const status = await getPermissionStatus();
      if (status === "granted") {
        const c = (await getCurrentCoords()) ?? SEOUL_CITY_HALL;
        s.setAnchor(c, "gps", c);
        setPerm("ready");
      } else {
        setPerm(status);
      }
    })();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const allow = async () => {
    const status = await requestPermission();
    if (status === "granted") {
      const c = (await getCurrentCoords()) ?? SEOUL_CITY_HALL;
      s.setAnchor(c, "gps", c);
      setPerm("ready");
    } else {
      setPerm("denied");
    }
  };

  const skipToSeoul = () => {
    s.setAnchor(SEOUL_CITY_HALL, "pan", null);
    setPerm("ready");
  };

  const recenter = async () => {
    if (s.gpsCoords) s.recenterToGps();
    else {
      const status = await getPermissionStatus();
      setPerm(status === "granted" ? "ready" : status);
      if (status === "granted") {
        const c = (await getCurrentCoords()) ?? SEOUL_CITY_HALL;
        s.setAnchor(c, "gps", c);
      }
    }
  };

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
        <View style={styles.pill} pointerEvents="box-none">
          <SearchHerePill onPress={() => s.searchHere()} />
        </View>
      ) : null}
      <View style={styles.fab} pointerEvents="box-none">
        <RecenterFab onPress={recenter} />
      </View>

      <MapBottomSheet
        snap={s.snap}
        onSnapChange={s.setSnap}
        headerExtra={<CategoryChips value={s.category} onChange={s.setCategory} />}
      >
        {nearby.isLoading ? (
          <View style={styles.list}>
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
          <View style={styles.center}>
            <Text style={styles.dim}>주변 정보를 불러오지 못했어요</Text>
            <Pressable style={styles.retry} onPress={() => nearby.refetch()}>
              <Text style={styles.retryText}>다시 시도</Text>
            </Pressable>
          </View>
        ) : spots.length === 0 ? (
          <View style={styles.center}>
            <Text style={styles.dim}>이 주변엔 아직 추천 스팟이 없어요</Text>
            <Text style={styles.dimSub}>
              지도를 옮겨 &apos;이 지역에서 검색&apos;을 누르거나, 다른 지역을 선택해 보세요
            </Text>
          </View>
        ) : (
          <ScrollView
            showsVerticalScrollIndicator={false}
            contentContainerStyle={{ paddingBottom: spacing.xxl }}
          >
            {spots.map((spot) => (
              <NearbyCard
                key={spot.contentId}
                spot={spot}
                selected={spot.contentId === s.selectedSpotId}
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
  pill: { position: "absolute", left: 0, right: 0, bottom: "60%" },
  fab: { position: "absolute", right: spacing.lg, bottom: "60%" },
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
