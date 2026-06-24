import { View, Text, Image, StyleSheet } from "react-native";
import { Icon } from "@/components/Icon";
import { colors } from "@/constants/theme";
import { MiniStatusBar } from "./MiniStatusBar";

/** STEP 1 preview: "사진 선택" screen (.scr-select). Rendered inside the 392px design frame. */
export function MiniSelectScreen() {
  return (
    <View style={styles.root}>
      <MiniStatusBar />
      <Text style={styles.title}>{"사진 속 분위기로\n여행지를 찾아요"}</Text>
      <View style={styles.preview}>
        <Image
          source={{ uri: "https://picsum.photos/seed/select/520/700" }}
          style={styles.previewImg}
        />
        <View style={styles.remove}>
          <Icon name="close" size={18} color={colors.onImage} strokeWidth={2.2} />
        </View>
      </View>
      <View style={styles.acts}>
        <View style={styles.actBtn}>
          <Icon name="camera" size={20} color={colors.ink} strokeWidth={1.8} />
          <Text style={styles.actLabel}>촬영</Text>
        </View>
        <View style={styles.actBtn}>
          <Icon name="image" size={20} color={colors.ink} strokeWidth={1.8} />
          <Text style={styles.actLabel}>갤러리</Text>
        </View>
      </View>
      <View style={styles.cta}>
        <Icon name="sparkle" size={19} color={colors.onImage} />
        <Text style={styles.ctaLabel}>분석하기</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg, paddingHorizontal: 24, paddingBottom: 22 },
  title: {
    fontSize: 25,
    fontWeight: "700",
    letterSpacing: -0.55,
    lineHeight: 32,
    marginTop: 6,
    color: colors.ink,
  },
  preview: {
    flex: 1,
    marginVertical: 22,
    marginBottom: 16,
    borderRadius: 20,
    overflow: "hidden",
    backgroundColor: colors.inset,
  },
  previewImg: { width: "100%", height: "100%" },
  remove: {
    position: "absolute",
    top: 12,
    right: 12,
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: colors.control,
    alignItems: "center",
    justifyContent: "center",
  },
  acts: { flexDirection: "row", gap: 11, marginBottom: 11 },
  actBtn: {
    flex: 1,
    height: 54,
    borderRadius: 12,
    backgroundColor: colors.inset,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
  },
  actLabel: { fontSize: 15, fontWeight: "700", color: colors.ink },
  cta: {
    height: 56,
    borderRadius: 12,
    backgroundColor: colors.ink,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
  },
  ctaLabel: { fontSize: 16, fontWeight: "700", color: colors.onImage },
});
