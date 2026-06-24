import { View, Text, Pressable, Linking, StyleSheet } from "react-native";
import Svg, { Path, Circle, Line } from "react-native-svg";
import type { SpotDetail } from "@/lib/api-types";
import { Icon } from "@/components/Icon";
import type { IconName } from "@/components/Icon";
import { colors } from "@/constants/theme";

const GRID = 36;
const MAP_W = 362; // phone width 402 - 2*20 padding (approx; flex stretches it)
const MAP_H = 200;

function MapPreview() {
  const cols = Math.ceil(MAP_W / GRID);
  const rows = Math.ceil(MAP_H / GRID);
  return (
    <View style={styles.map}>
      <Svg style={StyleSheet.absoluteFill} width="100%" height="100%">
        {Array.from({ length: rows }).map((_, r) => (
          <Line
            key={`h${r}`}
            x1={0}
            y1={r * GRID}
            x2={MAP_W * 2}
            y2={r * GRID}
            stroke={colors.line}
            strokeWidth={1}
          />
        ))}
        {Array.from({ length: cols * 2 }).map((_, c) => (
          <Line
            key={`v${c}`}
            x1={c * GRID}
            y1={0}
            x2={c * GRID}
            y2={MAP_H}
            stroke={colors.line}
            strokeWidth={1}
          />
        ))}
      </Svg>
      <Svg width={34} height={34} viewBox="0 0 24 24" fill="none">
        <Path
          d="M12 22s7-6.5 7-11a7 7 0 1 0-14 0c0 4.5 7 11 7 11z"
          fill={colors.ink}
          stroke="#fff"
          strokeWidth={1.4}
        />
        <Circle cx={12} cy={11} r={2.6} fill="#fff" />
      </Svg>
    </View>
  );
}

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

  const openNaver = () => {
    const fallback = `https://map.naver.com/v5/search/${q}`;
    Linking.openURL(`nmap://search?query=${q}`).catch(() => Linking.openURL(fallback));
  };
  const openKakao = () => {
    const url =
      lat != null && lng != null
        ? `https://map.kakao.com/link/map/${q},${lat},${lng}`
        : `https://map.kakao.com/link/search/${q}`;
    Linking.openURL(url);
  };

  return (
    <View style={styles.section}>
      <Text style={styles.h2}>위치</Text>
      <MapPreview />
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
        {spot.homepage ? (
          <InfoRow
            icon="globe"
            value={spot.homepage}
            link
            onPress={() => Linking.openURL(spot.homepage as string)}
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
    height: MAP_H,
    borderRadius: 12,
    overflow: "hidden",
    backgroundColor: "#e8eaee",
    marginBottom: 14,
    alignItems: "center",
    justifyContent: "center",
  },
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
