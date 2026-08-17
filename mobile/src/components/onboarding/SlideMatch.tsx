import { StyleSheet, Text, View } from "react-native";
import { PreviewImage } from "@/components/onboarding/PreviewImage";
import { colors, spacing } from "@/constants/theme";

const MATCHES = [
  {
    title: "환호공원 스페이스워크",
    region: "경북 포항",
    source: require("../../../assets/onboarding/match-spacewalk.jpg"),
  },
  {
    title: "롯데월드타워",
    region: "서울 송파",
    source: require("../../../assets/onboarding/match-lotte.jpg"),
  },
  {
    title: "청사포 다릿돌전망대",
    region: "부산 해운대",
    source: require("../../../assets/onboarding/match-cheongsapo.jpg"),
  },
];

export function SlideMatch() {
  return (
    <View style={styles.wrap}>
      <View style={styles.mosaic}>
        <PreviewImage
          source={require("../../../assets/onboarding/overseas-eiffel.jpg")}
          scrim="tile"
          style={styles.big}
        >
          <View style={styles.pill}>
            <Text style={styles.pillText}>프랑스 에펠탑</Text>
          </View>
        </PreviewImage>
        <View style={styles.thumbCol}>
          <PreviewImage
            source={require("../../../assets/onboarding/overseas-denali.jpg")}
            style={styles.thumb}
          />
          <PreviewImage
            source={require("../../../assets/onboarding/overseas-alhambra.jpg")}
            style={styles.thumb}
          />
        </View>
      </View>
      <View style={styles.chip}>
        <Text style={styles.chipText}>닮은 국내 여행지 3곳</Text>
      </View>
      <View style={styles.matches}>
        {MATCHES.map((m) => (
          <View key={m.title} style={styles.matchCard}>
            <PreviewImage source={m.source} style={styles.matchImage} />
            <Text style={styles.matchTitle}>{m.title}</Text>
            <Text style={styles.matchRegion}>{m.region}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { alignSelf: "stretch", paddingHorizontal: spacing.xl, marginTop: spacing.md },
  mosaic: { flexDirection: "row", gap: 2, alignSelf: "center" },
  big: { width: 180, height: 180, borderTopLeftRadius: 14, borderBottomLeftRadius: 14 },
  thumbCol: { gap: 2 },
  thumb: { width: 89, height: 89, borderTopRightRadius: 14, borderBottomRightRadius: 14 },
  pill: {
    position: "absolute",
    left: 8,
    bottom: 8,
    paddingHorizontal: 9,
    paddingVertical: 4,
    borderRadius: 999,
    backgroundColor: colors.control,
  },
  pillText: { fontSize: 10.5, fontWeight: "700", color: colors.onImage },
  chip: {
    alignSelf: "center",
    marginTop: spacing.lg,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 999,
    backgroundColor: colors.accentFill,
  },
  chipText: { fontSize: 12, fontWeight: "800", color: colors.accentText },
  matches: { flexDirection: "row", gap: 8, marginTop: spacing.md },
  matchCard: {
    flex: 1,
    borderRadius: 12,
    backgroundColor: colors.inset,
    borderWidth: 1,
    borderColor: colors.line,
    padding: 8,
  },
  matchImage: { height: 60, borderRadius: 8 },
  matchTitle: { fontSize: 12, fontWeight: "800", color: colors.ink, marginTop: 7 },
  matchRegion: { fontSize: 10.5, fontWeight: "600", color: colors.sec, marginTop: 2 },
});
