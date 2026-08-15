import { useState } from "react";
import { View, Text, Pressable, ScrollView, StyleSheet } from "react-native";
import { Icon, type IconName } from "@/components/Icon";
import { colors, spacing, radii } from "@/constants/theme";

interface OptionalAccess {
  key: string;
  icon: IconName;
  label: string;
  why: string;
  whenDenied: string;
}

const OPTIONAL_ACCESS: OptionalAccess[] = [
  {
    key: "photo",
    icon: "photo",
    label: "사진 · 카메라",
    why: "고른 사진 한 장으로 닮은 여행지를 찾을 때만 써요.",
    whenDenied:
      "앱이 보관함 전체를 읽지 않아요. 시스템 선택기에서 고른 한 장만 전달돼요. 카메라를 거부해도 저장된 사진으로 검색할 수 있어요.",
  },
  {
    key: "location",
    icon: "location",
    label: "위치",
    why: "지도에서 내 주변 여행지를 보여줄 때만 써요.",
    whenDenied: "거부하면 서울 도심을 기준으로 지도를 볼 수 있어요.",
  },
];

export const DENIED_TOGGLE_LABEL = "허용하지 않으면 어떻게 되나요?";

export function AccessNotice() {
  const [deniedOpen, setDeniedOpen] = useState(false);

  return (
    <ScrollView
      style={styles.root}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
    >
      <Text style={styles.eyebrow}>접근권한 안내</Text>
      <Text style={styles.h2}>필요할 때만 물어볼게요</Text>
      <Text style={styles.sub}>
        카메라와 위치는 그 기능을 처음 쓰는 순간에만 허용을 물어봐요. 지금 미리 허용할 필요는
        없어요.
      </Text>

      <View style={styles.block}>
        <Text style={styles.blockTitle}>필수 접근권한</Text>
        <Text style={styles.blockBody}>
          없어요. 아무 권한도 허용하지 않아도 추천 피드와 여행지 정보를 모두 볼 수 있어요.
        </Text>
      </View>

      <View style={styles.block}>
        <Text style={styles.blockTitle}>선택 접근권한</Text>
        {OPTIONAL_ACCESS.map((a) => (
          <View key={a.key} style={styles.row}>
            <View style={styles.rowIcon}>
              <Icon name={a.icon} size={19} color={colors.sec} />
            </View>
            <View style={styles.rowMain}>
              <Text style={styles.rowLabel}>{a.label}</Text>
              <Text style={styles.rowWhy}>{a.why}</Text>
              {deniedOpen ? <Text style={styles.rowDenied}>{a.whenDenied}</Text> : null}
            </View>
          </View>
        ))}
        <Pressable
          testID="access-denied-toggle"
          accessibilityRole="button"
          accessibilityLabel={DENIED_TOGGLE_LABEL}
          accessibilityState={{ expanded: deniedOpen }}
          hitSlop={6}
          onPress={() => setDeniedOpen((open) => !open)}
          style={styles.toggle}
        >
          <Text style={styles.toggleText}>{DENIED_TOGGLE_LABEL}</Text>
          <Icon
            name={deniedOpen ? "chevron-up" : "chevron-down"}
            size={15}
            color={colors.ter}
            strokeWidth={2}
          />
        </Pressable>
      </View>

      <Text style={styles.foot}>허용 여부는 기기 설정에서 언제든 바꿀 수 있어요.</Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  content: {
    paddingTop: 8,
    paddingHorizontal: spacing.xl,
    paddingBottom: spacing.xl,
  },
  eyebrow: { fontSize: 12, fontWeight: "800", letterSpacing: 1.5, color: colors.accentText },
  h2: {
    fontSize: 22,
    fontWeight: "800",
    letterSpacing: -0.5,
    lineHeight: 28,
    color: colors.ink,
    marginTop: spacing.md,
  },
  sub: { fontSize: 14, lineHeight: 21, color: colors.sec, marginTop: 9 },
  block: {
    marginTop: spacing.lg,
    padding: spacing.md,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.inset,
    gap: spacing.sm,
  },
  blockTitle: { fontSize: 13, fontWeight: "800", color: colors.ink, letterSpacing: -0.2 },
  blockBody: { fontSize: 13, lineHeight: 20, color: colors.sec },
  row: { flexDirection: "row", gap: spacing.sm },
  rowIcon: { width: 24, alignItems: "center", paddingTop: 1 },
  rowMain: { flex: 1, gap: 3 },
  rowLabel: { fontSize: 14.5, fontWeight: "700", color: colors.ink },
  rowWhy: { fontSize: 13, lineHeight: 19, color: colors.sec },
  rowDenied: { fontSize: 12.5, lineHeight: 18, color: colors.ter },
  toggle: { flexDirection: "row", alignItems: "center", gap: 4, paddingTop: 2 },
  toggleText: { fontSize: 12.5, fontWeight: "600", letterSpacing: -0.2, color: colors.ter },
  foot: { fontSize: 12.5, lineHeight: 18, color: colors.ter, marginTop: spacing.md },
});
