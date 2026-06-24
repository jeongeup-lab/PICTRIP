import { View, Text, Image, StyleSheet } from "react-native";
import Svg, { Circle } from "react-native-svg";
import { colors } from "@/constants/theme";
import { MiniStatusBar } from "./MiniStatusBar";

/** Circular match-score badge (.gg) — a progress ring with a centered number. */
function ScoreBadge({ value }: { value: number }) {
  const size = 44;
  const stroke = 4.5;
  const r = (size - stroke) / 2;
  const circ = 2 * Math.PI * r;
  return (
    <View style={[styles.badge, { width: size, height: size }]}>
      <Svg width={size} height={size} style={StyleSheet.absoluteFill}>
        <Circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke="rgba(255,255,255,0.25)"
          strokeWidth={stroke}
          fill="none"
        />
        <Circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke={colors.onImage}
          strokeWidth={stroke}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={circ}
          strokeDashoffset={circ * (1 - value / 100)}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </Svg>
      <View style={styles.badgeHole}>
        <Text style={styles.badgeNum}>{value}</Text>
      </View>
    </View>
  );
}

interface ResultCardProps {
  uri: string;
  name: string;
  meta: string;
  score: number;
}

function ResultCard({ uri, name, meta, score }: ResultCardProps) {
  return (
    <View style={styles.card}>
      <Image source={{ uri }} style={styles.cardImg} />
      <View style={styles.glass}>
        <View style={styles.glassText}>
          <Text style={styles.glassName}>{name}</Text>
          <Text style={styles.glassMeta}>{meta}</Text>
        </View>
        <ScoreBadge value={score} />
      </View>
    </View>
  );
}

/** STEP 3 preview: "결과" screen (.scr-res). Rendered inside the 392px design frame. */
export function MiniResultScreen() {
  return (
    <View style={styles.root}>
      <View style={styles.hero}>
        <Image source={{ uri: "https://picsum.photos/seed/hero/784/600" }} style={styles.heroImg} />
        <View style={styles.heroScrimTop} pointerEvents="none" />
        <View style={styles.heroScrimBottom} pointerEvents="none" />
        <MiniStatusBar onImage overlay />
        <View style={styles.heroTitle}>
          <Text style={styles.heroEyebrow}>내 사진과 닮은</Text>
          <Text style={styles.heroHeading}>비슷한 장소 24곳</Text>
        </View>
      </View>
      <View style={styles.pills}>
        <View style={[styles.pill, styles.pillOn]}>
          <Text style={styles.pillOnText}>유사도순</Text>
        </View>
        <View style={[styles.pill, styles.pillOff]}>
          <Text style={styles.pillOffText}>거리순</Text>
        </View>
      </View>
      <ResultCard
        uri="https://picsum.photos/seed/r1/740/340"
        name="곽지해수욕장"
        meta="해변 · 3.4km"
        score={96}
      />
      <ResultCard
        uri="https://picsum.photos/seed/r2/740/340"
        name="함덕해수욕장"
        meta="해변 · 18km"
        score={93}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  hero: { height: 300 },
  heroImg: { width: "100%", height: "100%" },
  heroScrimTop: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    height: 70,
    backgroundColor: colors.scrim,
  },
  heroScrimBottom: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    height: 160,
    backgroundColor: colors.scrimStrong,
  },
  heroTitle: { position: "absolute", left: 22, bottom: 20 },
  heroEyebrow: {
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 2,
    color: colors.onImage,
    opacity: 0.82,
  },
  heroHeading: {
    fontSize: 27,
    fontWeight: "800",
    letterSpacing: -0.5,
    marginTop: 5,
    color: colors.onImage,
  },
  pills: { flexDirection: "row", gap: 7, paddingHorizontal: 20, paddingTop: 16, paddingBottom: 8 },
  pill: { paddingHorizontal: 15, paddingVertical: 8, borderRadius: 999 },
  pillOn: { backgroundColor: colors.ink },
  pillOnText: { fontSize: 13, fontWeight: "700", color: colors.onImage },
  pillOff: { backgroundColor: colors.fill },
  pillOffText: { fontSize: 13, fontWeight: "700", color: colors.sec },
  card: {
    marginHorizontal: 20,
    marginTop: 6,
    height: 168,
    borderRadius: 20,
    overflow: "hidden",
  },
  cardImg: { width: "100%", height: "100%" },
  glass: {
    position: "absolute",
    left: 12,
    right: 12,
    bottom: 12,
    height: 60,
    borderRadius: 15,
    backgroundColor: "rgba(20,18,22,0.42)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.14)",
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 16,
    gap: 14,
  },
  glassText: { flex: 1 },
  glassName: { fontSize: 17, fontWeight: "700", color: colors.onImage },
  glassMeta: { fontSize: 12.5, opacity: 0.86, marginTop: 2, color: colors.onImage },
  badge: { alignItems: "center", justifyContent: "center" },
  badgeHole: {
    width: 35,
    height: 35,
    borderRadius: 17.5,
    backgroundColor: "rgba(20,18,22,0.30)",
    alignItems: "center",
    justifyContent: "center",
  },
  badgeNum: { fontSize: 13, fontWeight: "800", color: colors.onImage },
});
