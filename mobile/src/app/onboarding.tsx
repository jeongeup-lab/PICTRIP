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
import { SafeAreaView } from "react-native-safe-area-context";
import { router } from "expo-router";
import { setOnboardingSeen } from "@/lib/storage";
import { Icon } from "@/components/Icon";
import { MiniDevice } from "@/components/onboarding/MiniDevice";
import { MiniSelectScreen } from "@/components/onboarding/MiniSelectScreen";
import { MiniAnalyzeScreen } from "@/components/onboarding/MiniAnalyzeScreen";
import { MiniResultScreen } from "@/components/onboarding/MiniResultScreen";
import { colors, spacing } from "@/constants/theme";

const SLIDES = [
  {
    key: "select",
    eyebrow: "STEP 1",
    h2: "마음에 든 사진을 골라요",
    sub: "여행 사진이든 인터넷에서 본 풍경이든, 한 장이면 충분해요",
    screen: <MiniSelectScreen />,
  },
  {
    key: "analyze",
    eyebrow: "STEP 2",
    h2: "AI가 분위기를 읽어요",
    sub: "사진의 색감과 분위기를 분석해 닮은 곳을 찾아요",
    screen: <MiniAnalyzeScreen />,
  },
  {
    key: "result",
    eyebrow: "STEP 3",
    h2: "닮은 여행지를 추천받아요",
    sub: "분위기가 비슷한 곳을 유사도 순으로 보여드려요",
    screen: <MiniResultScreen />,
  },
];

export default function Onboarding() {
  const { width } = useWindowDimensions();
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
      <Pressable style={styles.skip} onPress={finish} hitSlop={8}>
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
            <MiniDevice>{s.screen}</MiniDevice>
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
          <Icon name="camera" size={19} color={colors.onImage} strokeWidth={1.8} />
          <Text style={styles.ctaLabel}>사진으로 시작하기</Text>
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.inset },
  skip: {
    position: "absolute",
    top: spacing.lg,
    right: spacing.lg,
    zIndex: 9,
    padding: spacing.xs,
  },
  skipText: { color: colors.ter, fontSize: 14, fontWeight: "600" },
  track: { flex: 1, backgroundColor: colors.bg },
  slide: {
    flex: 1,
    alignItems: "center",
    paddingTop: 18,
    backgroundColor: colors.bg,
  },
  eyebrow: { fontSize: 12, fontWeight: "800", letterSpacing: 1.5, color: colors.ter },
  cap: { alignItems: "center", paddingTop: 22, paddingHorizontal: 36 },
  h2: {
    fontSize: 23,
    fontWeight: "800",
    letterSpacing: -0.5,
    lineHeight: 30,
    color: colors.ink,
    textAlign: "center",
  },
  sub: {
    fontSize: 14,
    lineHeight: 22,
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
  },
  dots: { flexDirection: "row", justifyContent: "center", gap: 7 },
  dot: { width: 7, height: 7, borderRadius: 3.5, backgroundColor: colors.line },
  dotOn: { width: 22, borderRadius: 4, backgroundColor: colors.ink },
  cta: {
    height: 54,
    borderRadius: 13,
    backgroundColor: colors.ink,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
  },
  ctaLabel: { fontSize: 16, fontWeight: "700", color: colors.onImage },
});
