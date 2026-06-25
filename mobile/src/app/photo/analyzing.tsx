import { useEffect, useState } from "react";
import { Animated, View, Text, Pressable, Image, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router } from "expo-router";
import { Icon } from "@/components/Icon";
import { usePhotoFlowStore } from "@/features/photo/stores/photo-flow-store";
import { useLoadingAnimation } from "@/features/photo/hooks/use-loading-animation";
import { MIN_VISIBLE_MS } from "@/features/photo/constants/timing";
import { colors, spacing, radii } from "@/constants/theme";

export default function PhotoAnalyzingScreen() {
  const insets = useSafeAreaInsets();
  const asset = usePhotoFlowStore((s) => s.asset);
  const status = usePhotoFlowStore((s) => s.status);
  const startSearch = usePhotoFlowStore((s) => s.startSearch);
  const abort = usePhotoFlowStore((s) => s.abort);

  const [mountedAt] = useState(() => Date.now());
  const { translateX } = useLoadingAnimation();

  useEffect(() => {
    if (status !== "success") return;
    const elapsed = Date.now() - mountedAt;
    const wait = Math.max(0, MIN_VISIBLE_MS - elapsed);
    const t = setTimeout(() => router.replace("/photo/result"), wait);
    return () => clearTimeout(t);
  }, [status, mountedAt]);

  const goBack = () => {
    abort();
    router.back();
  };

  const isError = status === "error";

  return (
    <View style={[styles.root, { paddingTop: insets.top + spacing.sm }]}>
      <Pressable style={styles.back} onPress={goBack} hitSlop={8}>
        <Icon name="chevron-left" size={23} />
      </Pressable>

      <View style={styles.wrap}>
        {asset ? <Image source={{ uri: asset.uri }} style={styles.thumb} /> : null}

        {isError ? (
          <>
            <Text style={styles.title}>분석하지 못했어요</Text>
            <Text style={styles.sub}>잠시 후 다시 시도해 주세요</Text>
            <View style={styles.errorActions}>
              <Pressable style={[styles.errBtn, styles.errPrimary]} onPress={() => startSearch()}>
                <Text style={styles.errPrimaryText}>다시 시도</Text>
              </Pressable>
              <Pressable style={styles.errBtn} onPress={() => router.back()}>
                <Text style={styles.errText}>돌아가기</Text>
              </Pressable>
            </View>
          </>
        ) : (
          <>
            <Text style={styles.title}>사진을 분석하고 있어요</Text>
            <Text style={styles.sub}>잠시만 기다려 주세요</Text>
            <View style={styles.bar}>
              <Animated.View style={[styles.barFill, { transform: [{ translateX }] }]} />
            </View>
          </>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  back: {
    width: 40,
    height: 40,
    alignItems: "center",
    justifyContent: "center",
    marginLeft: spacing.xs,
  },
  wrap: { flex: 1, alignItems: "center", justifyContent: "center", paddingHorizontal: 44 },
  thumb: {
    width: 92,
    height: 92,
    borderRadius: radii.xl,
    marginBottom: 26,
    backgroundColor: colors.inset,
  },
  title: {
    fontSize: 20,
    fontWeight: "700",
    letterSpacing: -0.36,
    marginBottom: 6,
    color: colors.ink,
  },
  sub: { fontSize: 13, color: colors.sec, marginBottom: 30 },
  bar: {
    width: "100%",
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.skeleton,
    overflow: "hidden",
  },
  barFill: { width: "42%", height: "100%", borderRadius: 2, backgroundColor: colors.ink },
  errorActions: { flexDirection: "row", gap: 11, marginTop: 4 },
  errBtn: {
    height: 48,
    paddingHorizontal: 22,
    borderRadius: radii.sm,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.inset,
  },
  errPrimary: { backgroundColor: colors.ink },
  errPrimaryText: { fontSize: 15, fontWeight: "700", color: colors.onImage },
  errText: { fontSize: 15, fontWeight: "700", color: colors.ink },
});
