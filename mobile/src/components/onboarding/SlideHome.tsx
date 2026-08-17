import { StyleSheet, Text, View } from "react-native";
import { PreviewImage } from "@/components/onboarding/PreviewImage";
import { colors, spacing } from "@/constants/theme";

const CHANNELS = [
  { label: "SPOT", source: require("../../../assets/onboarding/tile-spot.jpg"), fresh: true },
  { label: "CAFE", source: require("../../../assets/onboarding/tile-cafe.jpg"), fresh: true },
  { label: "FOOD", source: require("../../../assets/onboarding/tile-food.jpg"), fresh: false },
  { label: "FESTA", source: require("../../../assets/onboarding/tile-festa.jpg"), fresh: false },
  { label: "HIDDEN", source: require("../../../assets/onboarding/tile-hidden.jpg"), fresh: false },
];

const RANKS = [
  {
    rank: 1,
    title: "경복궁",
    meta: "1.2km · 관광지",
    source: require("../../../assets/onboarding/rank-gyeongbokgung.jpg"),
  },
  {
    rank: 2,
    title: "광화문광장",
    meta: "0.9km · 관광지",
    source: require("../../../assets/onboarding/rank-gwanghwamun.jpg"),
  },
];

export function SlideHome() {
  return (
    <View style={styles.card}>
      <View style={styles.rowHead}>
        <Text style={styles.rowTitle}>오늘 열린 채널</Text>
      </View>
      <View style={styles.tiles}>
        {CHANNELS.map((c) => (
          <PreviewImage key={c.label} source={c.source} scrim="tile" style={styles.tile}>
            {c.fresh ? <View style={styles.dot} /> : null}
            <Text style={styles.tileLabel}>{c.label}</Text>
          </PreviewImage>
        ))}
      </View>
      <View style={[styles.rowHead, styles.rowHeadRank]}>
        <Text style={styles.rowTitle}>내 주변 인기 장소</Text>
      </View>
      <View style={styles.ranks}>
        {RANKS.map((r) => (
          <View key={r.rank} style={styles.rankCard}>
            <PreviewImage source={r.source} scrim="card" style={styles.rankImage}>
              <Text style={styles.rankNumber}>{r.rank}</Text>
            </PreviewImage>
            <View style={styles.rankFooter}>
              <Text style={styles.rankTitle}>{r.title}</Text>
              <Text style={styles.rankMeta}>{r.meta}</Text>
            </View>
          </View>
        ))}
      </View>
      <Text style={styles.credit}>사진 · 한국관광공사</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    alignSelf: "stretch",
    marginHorizontal: 16,
    marginTop: spacing.md,
    paddingTop: 16,
    paddingHorizontal: spacing.md,
    paddingBottom: 18,
    borderRadius: 20,
    backgroundColor: colors.inset,
    borderWidth: 1,
    borderColor: colors.line,
  },
  rowHead: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 12,
  },
  rowHeadRank: { marginTop: spacing.lg, marginBottom: spacing.sm },
  rowTitle: { fontSize: 12, fontWeight: "800", letterSpacing: -0.2, color: colors.ink },
  tiles: { flexDirection: "row", gap: 8 },
  tile: { width: 62, height: 80, borderRadius: 11 },
  tileLabel: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 6,
    textAlign: "center",
    fontSize: 9.5,
    fontWeight: "800",
    color: colors.onImage,
  },
  dot: {
    position: "absolute",
    top: 6,
    right: 6,
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.accent,
    borderWidth: 1.5,
    borderColor: colors.onImage,
  },
  ranks: { flexDirection: "row", gap: 8 },
  rankCard: { flex: 1, borderRadius: 14, overflow: "hidden", backgroundColor: colors.inset },
  rankImage: { height: 104 },
  rankNumber: {
    position: "absolute",
    top: -2,
    left: 9,
    fontSize: 32,
    fontWeight: "900",
    fontStyle: "italic",
    letterSpacing: -1.6,
    color: colors.onImage,
  },
  rankFooter: { paddingTop: 8, paddingHorizontal: 10, paddingBottom: 10 },
  rankTitle: { fontSize: 12.5, fontWeight: "800", letterSpacing: -0.3, color: colors.ink },
  rankMeta: { fontSize: 11, fontWeight: "600", color: colors.sec, marginTop: 3 },
  credit: { fontSize: 10, fontWeight: "600", color: colors.ter, marginTop: 12 },
});
