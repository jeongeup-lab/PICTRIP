import { useRef, useState } from "react";
import {
  View,
  Text,
  ScrollView,
  Pressable,
  useWindowDimensions,
  StyleSheet,
  type NativeSyntheticEvent,
  type NativeScrollEvent,
} from "react-native";
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context";
import { router } from "expo-router";
import { setOnboardingSeen } from "@/lib/storage";
import { Icon } from "@/components/Icon";
import { MiniDevice } from "@/components/onboarding/MiniDevice";
import { colors, spacing, radii } from "@/constants/theme";

const SLIDES = [
  {
    key: "select",
    eyebrow: "STEP 1",
    h2: "마음에 든 사진을 골라요",
    sub: "여행 사진이든 인터넷에서 본 풍경이든, 한 장이면 충분해요",
  },
  {
    key: "analyze",
    eyebrow: "STEP 2",
    h2: "AI가 분위기를 읽어요",
    sub: "사진의 색감과 분위기를 분석해 닮은 곳을 찾아요",
  },
  {
    key: "result",
    eyebrow: "STEP 3",
    h2: "닮은 여행지를 추천받아요",
    sub: "분위기가 비슷한 곳을 유사도 순으로 보여드려요",
  },
];

export default function Onboarding() {
  const { width } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const [index, setIndex] = useState(0);
  const scrollRef = useRef<ScrollView>(null);

  const onScroll = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    setIndex(Math.round(e.nativeEvent.contentOffset.x / width));
  };

  const finish = async () => {
    await setOnboardingSeen();
    router.replace("/(tabs)");
  };

  return (
    <SafeAreaView style={styles.root} edges={["top", "bottom"]}>
      <Pressable
        style={[styles.skip, { top: insets.top + spacing.lg }]}
        onPress={finish}
        hitSlop={8}
      >
        <Text style={styles.skipText}>건너뛰기</Text>
      </Pressable>

      <ScrollView
        ref={scrollRef}
        horizontal
        pagingEnabled
        showsHorizontalScrollIndicator={false}
        onScroll={onScroll}
        scrollEventThrottle={16}
        style={styles.track}
      >
        {SLIDES.map((s) => (
          <View key={s.key} style={[styles.slide, { width }]}>
            <Text style={styles.eyebrow}>{s.eyebrow}</Text>
            <MiniDevice />
            <View style={styles.cap}>
              <Text style={styles.h2}>{s.h2}</Text>
              <Text style={styles.sub}>{s.sub}</Text>
            </View>
          </View>
        ))}
      </ScrollView>

      <View style={styles.foot}>
        <View style={styles.dots}>
          {SLIDES.map((s, i) => (
            <View key={s.key} style={[styles.dot, i === index && styles.dotOn]} />
          ))}
        </View>
        <Pressable style={styles.cta} onPress={finish}>
          <Icon name="camera" size={18} color={colors.onImage} strokeWidth={1.8} />
          <Text style={styles.ctaLabel}>사진으로 시작하기</Text>
        </Pressable>
        <Pressable onPress={finish} hitSlop={8}>
          <Text style={styles.aux}>
            이미 둘러본 적이 있다면 <Text style={styles.auxLink}>바로 시작</Text>
          </Text>
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.inset },
  skip: {
    position: "absolute",
    right: spacing.lg,
    zIndex: 9,
    padding: spacing.xs,
  },
  skipText: { color: colors.ter, fontSize: 14, fontWeight: "600" },
  track: { flex: 1, backgroundColor: colors.bg },
  slide: {
    flex: 1,
    alignItems: "center",
    paddingTop: 8,
    backgroundColor: colors.bg,
  },
  eyebrow: { fontSize: 12, fontWeight: "800", letterSpacing: 1.5, color: colors.accentText },
  cap: { alignItems: "center", paddingTop: 24, paddingHorizontal: 40 },
  h2: {
    fontSize: 22,
    fontWeight: "800",
    letterSpacing: -0.5,
    lineHeight: 28,
    color: colors.ink,
    textAlign: "center",
  },
  sub: {
    fontSize: 14,
    lineHeight: 21,
    color: colors.sec,
    marginTop: 9,
    textAlign: "center",
  },
  foot: {
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.md,
    paddingBottom: 26,
    gap: 16,
    backgroundColor: colors.inset,
    borderTopWidth: 1,
    borderTopColor: colors.line,
  },
  dots: { flexDirection: "row", justifyContent: "center", gap: 7 },
  dot: { width: 7, height: 7, borderRadius: 4, backgroundColor: colors.line },
  dotOn: { width: 22, backgroundColor: colors.accent },
  cta: {
    height: 52,
    borderRadius: radii.md,
    backgroundColor: colors.accent,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
  },
  ctaLabel: { fontSize: 15, fontWeight: "700", color: colors.onImage },
  aux: { fontSize: 12.5, color: colors.ter, textAlign: "center" },
  auxLink: { color: colors.sec, fontWeight: "700", textDecorationLine: "underline" },
});
