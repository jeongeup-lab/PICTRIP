import { StyleSheet, Text, View } from "react-native";
import { Icon } from "@/components/Icon";
import { PreviewImage } from "@/components/onboarding/PreviewImage";
import { colors, spacing } from "@/constants/theme";

const CHECKS = [
  { label: "사진 분위기를 읽었어요", value: "바다 · 한적" },
  { label: "근처 여행지를 찾았어요", value: "3곳" },
];

const SPOTS = [
  {
    title: "궁평항",
    meta: "경기 화성 · 62km",
    source: require("../../../assets/onboarding/chat-gungpyeong.jpg"),
  },
  {
    title: "제부도",
    meta: "경기 화성 · 58km",
    source: require("../../../assets/onboarding/chat-jebudo.jpg"),
  },
];

export function SlideChat() {
  return (
    <View style={styles.wrap}>
      <View style={styles.banner}>
        <PreviewImage
          source={require("../../../assets/onboarding/chat-attach.jpg")}
          style={styles.bannerThumb}
        />
        <View style={styles.bannerText}>
          <Text style={styles.bannerTitle}>이 사진 같은 분위기로 찾아요</Text>
          <Text style={styles.bannerSub}>사진은 저장하지 않아요</Text>
        </View>
        <Icon name="close" size={15} color={colors.sec} />
      </View>
      <View style={styles.userBubble}>
        <Text style={styles.userText}>서울에서 두 시간 안쪽으로 여기 같은 데 있을까?</Text>
      </View>
      <View style={styles.checks}>
        {CHECKS.map((c) => (
          <View key={c.label} style={styles.checkRow}>
            <Icon name="check" size={13} color={colors.positive} strokeWidth={2.4} />
            <Text style={styles.checkLabel}>{c.label}</Text>
            <Text style={styles.checkValue}>{c.value}</Text>
          </View>
        ))}
      </View>
      <Text style={styles.answer}>
        두 시간 안쪽으로 <Text style={styles.answerEm}>한적한 바다</Text> 세 곳을 골랐어요.
      </Text>
      <View style={styles.spots}>
        {SPOTS.map((s) => (
          <View key={s.title} style={styles.spotCard}>
            <PreviewImage source={s.source} style={styles.spotImage} />
            <View style={styles.spotBody}>
              <Text style={styles.spotTitle}>{s.title}</Text>
              <Text style={styles.spotMeta}>{s.meta}</Text>
            </View>
          </View>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { alignSelf: "stretch", paddingHorizontal: spacing.xl, marginTop: spacing.md, gap: 12 },
  banner: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    padding: 10,
    borderRadius: 14,
    backgroundColor: colors.accentFill,
  },
  bannerThumb: { width: 46, height: 46, borderRadius: 10 },
  bannerText: { flex: 1, gap: 2 },
  bannerTitle: { fontSize: 12.5, fontWeight: "700", color: colors.ink },
  bannerSub: { fontSize: 11, fontWeight: "600", color: colors.sec },
  userBubble: {
    alignSelf: "flex-end",
    maxWidth: "82%",
    backgroundColor: colors.accent,
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    borderBottomLeftRadius: 16,
    borderBottomRightRadius: 4,
  },
  userText: { fontSize: 13, fontWeight: "600", color: colors.onImage, lineHeight: 19 },
  checks: { gap: 6 },
  checkRow: { flexDirection: "row", alignItems: "center", gap: 7 },
  checkLabel: { fontSize: 12.5, fontWeight: "600", color: colors.sec },
  checkValue: { fontSize: 11.5, fontWeight: "800", color: colors.ink },
  answer: { fontSize: 13.5, lineHeight: 20, color: colors.ink },
  answerEm: { fontWeight: "800" },
  spots: { flexDirection: "row", gap: 8 },
  spotCard: {
    width: 148,
    borderRadius: 12,
    overflow: "hidden",
    backgroundColor: colors.inset,
    borderWidth: 1,
    borderColor: colors.line,
  },
  spotImage: { height: 68 },
  spotBody: { paddingHorizontal: 10, paddingVertical: 8 },
  spotTitle: { fontSize: 12.5, fontWeight: "800", color: colors.ink },
  spotMeta: { fontSize: 10.5, fontWeight: "600", color: colors.sec, marginTop: 2 },
});
