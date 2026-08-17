import { View, Text, Pressable, ScrollView, StyleSheet } from "react-native";
import Svg, { Circle, Path } from "react-native-svg";
import { Icon, type IconName } from "@/components/Icon";
import { colors, themeName } from "@/constants/theme";

const OPTIONAL_ACCESS: { key: string; icon: IconName; label: string; why: string }[] = [
  {
    key: "photo",
    icon: "photo",
    label: "사진 · 카메라",
    why: "사진 한 장으로 닮은 여행지 검색",
  },
  {
    key: "location",
    icon: "location",
    label: "위치 정보",
    why: "내 주변 인기 여행지 추천",
  },
];

const NOTES = [
  "선택적 접근 권한은 해당 기능을 처음 쓸 때 물어보며, 미동의해도 나머지 서비스는 그대로 이용할 수 있어요.",
  "[설정 > PICTRIP > 권한]에서 언제든 바꿀 수 있어요.",
];

const dark = themeName === "dark";

export function AccessNotice({ onConfirm }: { onConfirm: () => void }) {
  return (
    <View style={styles.stage}>
      <View style={styles.watermark} pointerEvents="none">
        <Text style={styles.wmLine}>
          Pic<Text style={styles.wmSub}>ture</Text>
        </Text>
        <Text style={styles.wmLine}>
          A<Text style={styles.wmSub}>ny</Text>
        </Text>
        <View style={styles.wmRow}>
          <Text style={styles.wmLine}>Trip</Text>
          <View style={styles.wmBar} />
        </View>
      </View>
      <View style={styles.scrim}>
        <ScrollView
          contentContainerStyle={styles.scroll}
          showsVerticalScrollIndicator={false}
          bounces={false}
        >
          <View style={styles.card}>
            <Text style={styles.title}>PICTRIP 앱 이용을 위한 권한 안내</Text>

            <Text style={styles.sectionTitle}>필수적 접근 권한</Text>
            <View style={styles.row}>
              <View style={styles.iconCircle}>
                <Svg width={22} height={22} viewBox="0 0 24 24" fill="none">
                  <Circle cx={12} cy={12} r={8.5} stroke={colors.sec} strokeWidth={1.8} />
                  <Path
                    d="M6 18L18 6"
                    stroke={colors.sec}
                    strokeWidth={1.8}
                    strokeLinecap="round"
                  />
                </Svg>
              </View>
              <Text style={styles.rowLabel}>필수적 접근 권한 없음</Text>
            </View>

            <Text style={styles.sectionTitle}>선택적 접근 권한</Text>
            {OPTIONAL_ACCESS.map((a, i) => (
              <View key={a.key} style={[styles.row, i > 0 && styles.rowNext]}>
                <View style={styles.iconCircle}>
                  <Icon name={a.icon} size={22} color={colors.sec} strokeWidth={1.8} />
                </View>
                <View style={styles.rowMain}>
                  <Text style={styles.rowLabel}>{a.label}</Text>
                  <Text style={styles.rowWhy}>{a.why}</Text>
                </View>
              </View>
            ))}

            <View style={styles.notes}>
              {NOTES.map((note) => (
                <View key={note} style={styles.noteRow}>
                  <Text style={styles.noteBullet}>·</Text>
                  <Text style={styles.noteText}>{note}</Text>
                </View>
              ))}
            </View>

            <Pressable
              testID="access-confirm"
              accessibilityRole="button"
              onPress={onConfirm}
              style={styles.cta}
            >
              <Text style={styles.ctaLabel}>확인</Text>
            </Pressable>
          </View>
        </ScrollView>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  stage: { flex: 1, backgroundColor: colors.bg },
  watermark: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    alignItems: "center",
    justifyContent: "center",
  },
  wmLine: {
    fontSize: 42,
    fontWeight: "800",
    letterSpacing: -1.6,
    lineHeight: 45,
    color: dark ? "#FFFFFF" : "rgba(55,56,60,0.20)",
  },
  wmSub: { color: dark ? "rgba(255,255,255,0.42)" : "rgba(112,115,124,0.16)" },
  wmRow: { flexDirection: "row", alignItems: "center", gap: 12 },
  wmBar: {
    width: 96,
    height: 3,
    backgroundColor: dark ? "#FF3B53" : "rgba(255,59,83,0.45)",
  },
  scrim: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: dark ? "rgba(6,8,12,0.72)" : "rgba(247,247,248,0.78)",
  },
  scroll: { flexGrow: 1, justifyContent: "center", paddingHorizontal: 16, paddingVertical: 24 },
  card: {
    borderRadius: 24,
    backgroundColor: dark ? "#1F2228" : "#FFFFFF",
    borderWidth: 1,
    borderColor: colors.line,
    paddingTop: 26,
    paddingHorizontal: 22,
    paddingBottom: 22,
    shadowColor: dark ? "#000000" : "#171717",
    shadowOpacity: dark ? 0.6 : 0.14,
    shadowRadius: dark ? 70 : 48,
    shadowOffset: { width: 0, height: dark ? 30 : 20 },
    elevation: 12,
  },
  title: { fontSize: 20, fontWeight: "800", letterSpacing: -0.5, color: colors.ink },
  sectionTitle: {
    fontSize: 15,
    fontWeight: "800",
    letterSpacing: -0.3,
    color: colors.ink,
    marginTop: 26,
  },
  row: { flexDirection: "row", alignItems: "center", gap: 14, marginTop: 14 },
  rowNext: { marginTop: 16 },
  iconCircle: {
    width: 48,
    height: 48,
    borderRadius: 24,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.fill,
  },
  rowMain: { flex: 1 },
  rowLabel: { fontSize: 15, fontWeight: "700", color: colors.ink },
  rowWhy: { fontSize: 13.5, color: colors.sec, marginTop: 4 },
  notes: { marginTop: 24, gap: 10 },
  noteRow: { flexDirection: "row", gap: 7 },
  noteBullet: { fontSize: 13, color: colors.ter },
  noteText: { flex: 1, fontSize: 13, lineHeight: 20, color: colors.ter },
  cta: {
    marginTop: 24,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.accent,
    alignItems: "center",
    justifyContent: "center",
  },
  ctaLabel: { fontSize: 16, fontWeight: "800", color: "#FFFFFF" },
});
