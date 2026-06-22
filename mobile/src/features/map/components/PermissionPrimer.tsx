import { View, Text, Pressable, Linking, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Icon } from "@/components/Icon";
import { colors, spacing, radii } from "@/constants/theme";

interface Props {
  variant: "priming" | "denied";
  onAllow: () => void;
  onSkip: () => void;
}

const COPY = {
  priming: {
    title: "내 주변 여행지를 보여드릴게요",
    body: "가까운 여행지부터 보여드려요. 위치는 추천에만 쓰고 저장하지 않아요.",
    primary: "위치 허용하기",
    secondary: "나중에 할게요",
  },
  denied: {
    title: "위치가 꺼져 있어요",
    body: "설정에서 위치를 켜면 내 주변 여행지를 추천해 드려요.",
    primary: "설정 열기",
    secondary: "둘러보기",
  },
} as const;

export function PermissionPrimer({ variant, onAllow, onSkip }: Props) {
  const insets = useSafeAreaInsets();
  const c = COPY[variant];
  const onPrimary = variant === "denied" ? () => Linking.openSettings() : onAllow;

  return (
    <View
      style={[styles.root, { paddingTop: insets.top, paddingBottom: insets.bottom + spacing.xl }]}
    >
      <View style={styles.body}>
        <View style={[styles.iconCircle, variant === "denied" && styles.iconMuted]}>
          <Icon name="location" size={34} color={variant === "denied" ? colors.ter : colors.ink} />
        </View>
        <Text style={styles.title}>{c.title}</Text>
        <Text style={styles.text}>{c.body}</Text>
      </View>
      <View style={styles.actions}>
        <Pressable style={styles.primary} onPress={onPrimary}>
          <Text style={styles.primaryText}>{c.primary}</Text>
        </Pressable>
        <Pressable style={styles.secondary} onPress={onSkip}>
          <Text style={styles.secondaryText}>{c.secondary}</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    position: "absolute",
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    backgroundColor: colors.bg,
    paddingHorizontal: spacing.xl,
    justifyContent: "space-between",
  },
  body: { flex: 1, alignItems: "center", justifyContent: "center", gap: spacing.md },
  iconCircle: {
    width: 84,
    height: 84,
    borderRadius: 42,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.fill,
    marginBottom: spacing.sm,
  },
  iconMuted: { backgroundColor: colors.inset },
  title: {
    fontSize: 22,
    fontWeight: "800",
    letterSpacing: -0.4,
    color: colors.ink,
    textAlign: "center",
  },
  text: { fontSize: 14, lineHeight: 22, color: colors.sec, textAlign: "center" },
  actions: { gap: spacing.sm },
  primary: {
    height: 54,
    borderRadius: radii.md,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.ink,
  },
  primaryText: { fontSize: 16, fontWeight: "700", color: colors.onImage },
  secondary: { height: 50, alignItems: "center", justifyContent: "center" },
  secondaryText: { fontSize: 15, fontWeight: "600", color: colors.sec },
});
