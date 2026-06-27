import { View, Text, Pressable, Linking, StyleSheet } from "react-native";
import type { SpotDetail, NearbySpot } from "@/lib/api-types";
import { Icon } from "@/components/Icon";
import type { IconName } from "@/components/Icon";
import { KakaoWebMap } from "@/features/map/components/KakaoWebMap";
import { cleanHomepage } from "@/lib/homepage";
import { colors } from "@/constants/theme";

function MapLink({ label, onPress }: { label: string; onPress: () => void }) {
  return (
    <Pressable style={styles.mapLink} onPress={onPress}>
      <Icon name="map-pin" size={18} color={colors.ink} />
      <Text style={styles.mapLinkText}>{label}</Text>
    </Pressable>
  );
}

function InfoRow({
  icon,
  value,
  link,
  onPress,
}: {
  icon: IconName;
  value: string;
  link?: boolean;
  onPress?: () => void;
}) {
  return (
    <Pressable style={styles.infoRow} onPress={onPress} disabled={!onPress}>
      <Icon name={icon} size={20} color={colors.ter} />
      <Text style={[styles.infoValue, link && styles.infoLink]} numberOfLines={2}>
        {value}
      </Text>
    </Pressable>
  );
}

export function LocationSection({ spot }: { spot: SpotDetail }) {
  const address = [spot.addr1, spot.addr2].filter(Boolean).join(" ");
  const q = encodeURIComponent(spot.title);
  const lat = spot.mapy;
  const lng = spot.mapx;
  const homepage = cleanHomepage(spot.homepage);

  // Single non-interactive pin for this spot. KakaoWebMap reads contentId/mapx/mapy.
  const pin: NearbySpot = {
    contentId: spot.contentId,
    title: spot.title,
    firstImageUrl: spot.firstImageUrl,
    category: spot.category,
    mapx: spot.mapx,
    mapy: spot.mapy,
    dist: null,
    regionName: spot.regionName,
    sigunguName: spot.sigunguName,
    overview: spot.overview,
  };

  const openNaver = () => {
    const fallback = `https://map.naver.com/v5/search/${q}`;
    Linking.openURL(`nmap://search?query=${q}`).catch(() => Linking.openURL(fallback));
  };
  const openKakao = () => {
    const url =
      lat != null && lng != null
        ? `https://map.kakao.com/link/map/${q},${lat},${lng}`
        : `https://map.kakao.com/link/search/${q}`;
    Linking.openURL(url).catch(() => {});
  };

  return (
    <View style={styles.section}>
      <Text style={styles.h2}>위치</Text>
      {lat != null && lng != null ? (
        // Non-interactive: pass touches to the page ScrollView (avoids a WKWebView
        // dead zone that swallows touchmove and blocks scroll over the map).
        <View style={styles.map} pointerEvents="none">
          <KakaoWebMap
            center={{ lat, lng }}
            pins={[pin]}
            userLocation={null}
            interactive={false}
            onPinTap={() => {}}
          />
        </View>
      ) : (
        <View style={[styles.map, styles.mapPlaceholder]}>
          <Text style={styles.placeholderText}>위치 정보가 없어요</Text>
        </View>
      )}
      <View style={styles.mapLinks}>
        <MapLink label="네이버 지도" onPress={openNaver} />
        <MapLink label="카카오 지도" onPress={openKakao} />
      </View>
      <View style={styles.info}>
        {address ? <InfoRow icon="map-pin" value={address} /> : null}
        <InfoRow icon="clock" value={spot.intro?.usetime ?? "상시 개방"} />
        {spot.tel ? (
          <InfoRow
            icon="phone"
            value={spot.tel}
            onPress={() => Linking.openURL(`tel:${spot.tel}`)}
          />
        ) : null}
        {homepage ? (
          <InfoRow
            icon="globe"
            value={homepage.label}
            link
            onPress={() => Linking.openURL(homepage.url)}
          />
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  section: { paddingHorizontal: 20, paddingTop: 30 },
  h2: {
    fontSize: 22,
    fontWeight: "800",
    letterSpacing: -0.44,
    color: colors.ink,
    marginBottom: 16,
  },
  map: {
    height: 200,
    borderRadius: 12,
    overflow: "hidden",
    backgroundColor: colors.inset,
    marginBottom: 14,
  },
  mapPlaceholder: { alignItems: "center", justifyContent: "center" },
  placeholderText: { color: colors.ter, fontSize: 14 },
  mapLinks: { flexDirection: "row", gap: 12, marginBottom: 4 },
  mapLink: {
    flex: 1,
    height: 54,
    borderRadius: 12,
    backgroundColor: colors.inset,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 9,
  },
  mapLinkText: { fontSize: 15, fontWeight: "700", color: colors.ink },
  info: { marginTop: 8 },
  infoRow: { flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 14 },
  infoValue: { flex: 1, fontSize: 15, color: colors.ink },
  infoLink: { textDecorationLine: "underline" },
});
