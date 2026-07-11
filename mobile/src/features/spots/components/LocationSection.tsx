import { useEffect, useState } from "react";
import {
  View,
  Text,
  Pressable,
  Linking,
  Clipboard,
  InteractionManager,
  StyleSheet,
} from "react-native";
import type { SpotDetail, NearbySpot } from "@/lib/api-types";
import { Icon } from "@/components/Icon";
import type { IconName } from "@/components/Icon";
import { KakaoWebMap } from "@/features/map/components/KakaoWebMap";
import { cleanHomepage } from "@/lib/homepage";
import { htmlToPlainText } from "@/lib/html-text";
import { colors, radii } from "@/constants/theme";

function MapLink({
  label,
  onPress,
  accent,
}: {
  label: string;
  onPress: () => void;
  accent?: boolean;
}) {
  return (
    <Pressable style={[styles.mapLink, accent && styles.mapLinkAccent]} onPress={onPress}>
      <Text style={[styles.mapLinkText, accent && styles.mapLinkTextAccent]}>{label}</Text>
    </Pressable>
  );
}

interface InfoItem {
  icon: IconName;
  value: string;
  link?: boolean;
  onPress?: () => void;
  onCopy?: () => void;
}

function InfoRow({ icon, value, link, onPress, onCopy, last }: InfoItem & { last: boolean }) {
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    if (!copied) return;
    const timer = setTimeout(() => setCopied(false), 1500);
    return () => clearTimeout(timer);
  }, [copied]);

  return (
    <View style={[styles.infoRow, !last && styles.infoRowDivider]}>
      <Icon name={icon} size={18} color={colors.ter} strokeWidth={1.8} />
      <Text style={[styles.infoValue, link && styles.infoLink]} numberOfLines={2} onPress={onPress}>
        {value}
      </Text>
      {onCopy ? (
        <Pressable
          style={[styles.copyBtn, copied && styles.copyBtnDone]}
          onPress={() => {
            onCopy();
            setCopied(true);
          }}
          hitSlop={6}
        >
          <Text style={[styles.copyText, copied && styles.copyTextDone]}>
            {copied ? "복사됨" : "복사"}
          </Text>
        </Pressable>
      ) : null}
    </View>
  );
}

export function LocationSection({ spot }: { spot: SpotDetail }) {
  // Defer the WKWebView boot (create + remote Kakao SDK fetch + kakao.maps.load)
  // until the nav transition settles, so it doesn't jank the page becoming
  // interactive. The map fills into its fixed-height box a moment later.
  const [mapReady, setMapReady] = useState(false);
  useEffect(() => {
    const task = InteractionManager.runAfterInteractions(() => setMapReady(true));
    return () => task.cancel();
  }, []);

  const address = [spot.addr1, spot.addr2].filter(Boolean).join(" ");
  const q = encodeURIComponent(spot.title);
  const lat = spot.mapy;
  const lng = spot.mapx;
  const homepage = cleanHomepage(spot.homepage);
  const usetime = spot.intro?.usetime ? htmlToPlainText(spot.intro.usetime) : null;

  // Single non-interactive pin for this spot. KakaoWebMap reads contentId/mapx/mapy.
  const pin: NearbySpot = {
    contentId: spot.contentId,
    title: spot.title,
    firstImageUrl: spot.firstImageUrl,
    category: spot.category,
    mapx: spot.mapx,
    mapy: spot.mapy,
    dist: null,
    categoryGroup: null, // single self-pin on the detail map → generic dot glyph
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

  const rows: InfoItem[] = [];
  if (address)
    rows.push({ icon: "map-pin", value: address, onCopy: () => Clipboard.setString(address) });
  rows.push({ icon: "clock", value: usetime || "상시 개방" });
  if (spot.tel)
    rows.push({
      icon: "phone",
      value: spot.tel,
      link: true,
      onPress: () => Linking.openURL(`tel:${spot.tel}`),
    });
  if (homepage)
    rows.push({
      icon: "globe",
      value: homepage.label,
      link: true,
      onPress: () => Linking.openURL(homepage.url),
    });

  return (
    <View style={styles.section}>
      <Text style={styles.h2}>위치</Text>
      {lat != null && lng != null ? (
        // Non-interactive: pass touches to the page ScrollView (avoids a WKWebView
        // dead zone that swallows touchmove and blocks scroll over the map).
        <View style={styles.map} pointerEvents="none">
          {mapReady ? (
            <KakaoWebMap
              center={{ lat, lng }}
              pins={[pin]}
              userLocation={null}
              interactive={false}
              accentDot
              onPinTap={() => {}}
            />
          ) : null}
        </View>
      ) : (
        <View style={[styles.map, styles.mapPlaceholder]}>
          <Text style={styles.placeholderText}>위치 정보가 없어요</Text>
        </View>
      )}
      <View style={styles.mapLinks}>
        <MapLink label="네이버 지도" onPress={openNaver} accent />
        <MapLink label="카카오 지도" onPress={openKakao} />
      </View>
      <View style={styles.info}>
        {rows.map((r, i) => (
          <InfoRow key={r.icon} {...r} last={i === rows.length - 1} />
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  section: { paddingHorizontal: 20, paddingTop: 20 },
  h2: {
    fontSize: 19,
    fontWeight: "800",
    letterSpacing: -0.4,
    color: colors.ink,
    marginBottom: 14,
  },
  map: {
    height: 170,
    borderRadius: radii.md,
    overflow: "hidden",
    backgroundColor: colors.inset,
    borderWidth: 1,
    borderColor: colors.fillStrong,
    marginBottom: 12,
  },
  mapPlaceholder: { alignItems: "center", justifyContent: "center" },
  placeholderText: { color: colors.ter, fontSize: 14 },
  mapLinks: { flexDirection: "row", gap: 10, marginBottom: 6 },
  mapLink: {
    flex: 1,
    height: 48,
    borderRadius: radii.md,
    backgroundColor: colors.inset,
    alignItems: "center",
    justifyContent: "center",
  },
  mapLinkAccent: { backgroundColor: colors.accentFill },
  mapLinkText: { fontSize: 14, fontWeight: "700", color: colors.ink },
  mapLinkTextAccent: { color: colors.accentText },
  info: { marginTop: 2 },
  infoRow: { flexDirection: "row", alignItems: "center", gap: 11, paddingVertical: 13 },
  infoRowDivider: { borderBottomWidth: 1, borderBottomColor: "rgba(112,115,124,0.12)" },
  infoValue: { flex: 1, fontSize: 14.5, color: colors.ink },
  infoLink: { color: colors.accentText, textDecorationLine: "underline" },
  copyBtn: {
    borderWidth: 1,
    borderColor: "rgba(112,115,124,0.22)",
    borderRadius: radii.sm,
    paddingVertical: 4,
    paddingHorizontal: 9,
  },
  copyBtnDone: { borderColor: colors.accentText, backgroundColor: colors.accentFill },
  copyText: { fontSize: 12.5, fontWeight: "700", color: colors.sec },
  copyTextDone: { color: colors.accentText },
});
