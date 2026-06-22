import { useEffect, useState } from "react";
import { View, Text, Pressable, Image, Linking, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router } from "expo-router";
import { Icon } from "@/components/Icon";
import { usePhotoFlowStore } from "@/features/photo/stores/photo-flow-store";
import {
  pickFromLibrary,
  captureFromCamera,
  type PickResult,
} from "@/features/photo/usecases/pick-image";
import { colors, spacing, radii } from "@/constants/theme";

export default function PhotoSelectScreen() {
  const insets = useSafeAreaInsets();
  const asset = usePhotoFlowStore((s) => s.asset);
  const setAsset = usePhotoFlowStore((s) => s.setAsset);
  const clearAsset = usePhotoFlowStore((s) => s.clearAsset);
  const startSearch = usePhotoFlowStore((s) => s.startSearch);
  const reset = usePhotoFlowStore((s) => s.reset);
  const [cameraDenied, setCameraDenied] = useState(false);

  // 08 is the root of the photo stack — it unmounts exactly when the flow ends
  // (modal dismissed or replaced into spot detail). Release the image then (KTO).
  useEffect(() => () => reset(), [reset]);

  const handle = (result: PickResult) => {
    if (result === "permission-denied") {
      setCameraDenied(true);
      return;
    }
    if (result === "canceled") return;
    setCameraDenied(false);
    setAsset(result);
  };

  const analyze = () => {
    if (!asset) return;
    startSearch();
    router.push("/photo/analyzing");
  };

  return (
    <View style={[styles.root, { paddingTop: insets.top + spacing.sm }]}>
      <Pressable style={styles.back} onPress={() => router.back()} hitSlop={8}>
        <Icon name="chevron-left" size={23} />
      </Pressable>

      <View style={styles.body}>
        <Text style={styles.title}>사진 속 분위기로{"\n"}여행지를 찾아요</Text>
        <Text style={styles.sub}>마음에 드는 사진 한 장이면 충분해요.</Text>

        <View style={styles.preview}>
          {asset ? (
            <>
              <Image source={{ uri: asset.uri }} style={styles.previewImg} />
              <Pressable style={styles.remove} onPress={clearAsset} hitSlop={8}>
                <Icon name="close" size={18} color={colors.onImage} />
              </Pressable>
            </>
          ) : (
            <View style={styles.placeholder}>
              <Text style={styles.placeholderText}>사진을 고르세요</Text>
            </View>
          )}
        </View>

        {cameraDenied ? (
          <Pressable onPress={() => Linking.openSettings()}>
            <Text style={styles.denied}>설정에서 카메라 권한을 켜 주세요</Text>
          </Pressable>
        ) : null}

        <View style={styles.actions}>
          <Pressable style={styles.btn} onPress={async () => handle(await captureFromCamera())}>
            <Icon name="camera" size={20} />
            <Text style={styles.btnText}>촬영</Text>
          </Pressable>
          <Pressable style={styles.btn} onPress={async () => handle(await pickFromLibrary())}>
            <Icon name="image" size={20} />
            <Text style={styles.btnText}>갤러리</Text>
          </Pressable>
        </View>

        <Pressable
          style={[styles.cta, !asset && styles.ctaDisabled]}
          onPress={analyze}
          disabled={!asset}
        >
          <Icon name="sparkle" size={19} color={colors.onImage} />
          <Text style={styles.ctaText}>분석하기</Text>
        </Pressable>
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
  body: { flex: 1, paddingHorizontal: spacing.xl, paddingBottom: spacing.lg },
  title: {
    fontSize: 25,
    fontWeight: "700",
    letterSpacing: -0.55,
    lineHeight: 32,
    color: colors.ink,
  },
  sub: { color: colors.sec, fontSize: 14, marginTop: 8 },
  preview: {
    flex: 1,
    marginVertical: spacing.md,
    borderRadius: radii.xl,
    overflow: "hidden",
    backgroundColor: colors.inset,
  },
  previewImg: { width: "100%", height: "100%" },
  placeholder: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1.5,
    borderColor: colors.line,
    borderStyle: "dashed",
    borderRadius: radii.xl,
  },
  placeholderText: { color: colors.ter, fontSize: 15, fontWeight: "600" },
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
  denied: {
    color: colors.sec,
    fontSize: 13,
    marginBottom: spacing.sm,
    textDecorationLine: "underline",
  },
  actions: { flexDirection: "row", gap: 11, marginBottom: 11 },
  btn: {
    flex: 1,
    height: 54,
    borderRadius: radii.sm,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    backgroundColor: colors.inset,
  },
  btnText: { fontSize: 15, fontWeight: "700", color: colors.ink },
  cta: {
    height: 56,
    borderRadius: radii.sm,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    backgroundColor: colors.ink,
  },
  ctaDisabled: { backgroundColor: colors.ter },
  ctaText: { fontSize: 16, fontWeight: "700", color: colors.onImage },
});
