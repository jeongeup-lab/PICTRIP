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
import { getPermissionStatus, requestPermission } from "@/features/map/usecases/request-location";
import { SlideChat } from "@/components/onboarding/SlideChat";
import { SlideHome } from "@/components/onboarding/SlideHome";
import { SlideMatch } from "@/components/onboarding/SlideMatch";
import { AccessNotice } from "@/features/consent/components/AccessNotice";
import { colors, spacing, radii } from "@/constants/theme";

const SLIDES = [
  {
    key: "home",
    eyebrow: "STEP 1",
    h2: "열자마자\n오늘 갈 곳이 정해져요",
    sub: "요즘 뜨는 곳부터 숨은 명소까지\n매일 새로 골라 둬요",
    Preview: SlideHome,
  },
  {
    key: "match",
    eyebrow: "STEP 2",
    h2: "사진 한 장이면\n닮은 곳을 찾아요",
    sub: "해외 게시물을 누르면 분위기가 닮은\n국내 여행지를 바로 이어드려요",
    Preview: SlideMatch,
  },
  {
    key: "chat",
    eyebrow: "STEP 3",
    h2: "말로 물어봐도 돼요",
    sub: "“바다 보이는 카페” 처럼 편하게요",
    Preview: SlideChat,
  },
];

export default function Onboarding() {
  const { width } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const [index, setIndex] = useState(0);
  const [phase, setPhase] = useState<"tour" | "access">("tour");
  const scrollRef = useRef<ScrollView>(null);

  const onScroll = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    setIndex(Math.round(e.nativeEvent.contentOffset.x / width));
  };

  const showAccess = () => setPhase("access");

  const next = () => {
    if (index >= SLIDES.length - 1) {
      showAccess();
      return;
    }
    scrollRef.current?.scrollTo({ x: (index + 1) * width, animated: true });
  };

  const finish = async () => {
    await setOnboardingSeen();
    const status = await getPermissionStatus().catch(() => "denied" as const);
    if (status === "undetermined") {
      await requestPermission().catch(() => undefined);
    }
    router.replace("/(tabs)");
  };

  const lastSlide = index === SLIDES.length - 1;

  return (
    <SafeAreaView style={styles.root} edges={["top", "bottom"]}>
      {phase === "tour" ? (
        <>
          <Pressable
            style={[styles.skip, { top: insets.top + spacing.lg }]}
            onPress={showAccess}
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
            {SLIDES.map(({ key, eyebrow, h2, sub, Preview }) => (
              <View key={key} style={[styles.slide, { width }]}>
                <Preview />
                <View style={styles.cap}>
                  <Text style={styles.eyebrow}>{eyebrow}</Text>
                  <Text style={styles.h2}>{h2}</Text>
                  <Text style={styles.sub}>{sub}</Text>
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
            <Pressable style={styles.cta} onPress={next}>
              <Text style={styles.ctaLabel}>{lastSlide ? "시작하기" : "다음"}</Text>
            </Pressable>
            {lastSlide ? (
              <Pressable onPress={showAccess} hitSlop={8}>
                <Text style={styles.aux}>로그인 없이 둘러보기</Text>
              </Pressable>
            ) : null}
          </View>
        </>
      ) : (
        <AccessNotice onConfirm={() => void finish()} />
      )}
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
  skipText: { color: colors.sec, fontSize: 13.5, fontWeight: "600" },
  track: { flex: 1, backgroundColor: colors.bg },
  slide: {
    flex: 1,
    alignItems: "center",
    paddingTop: 56,
    backgroundColor: colors.bg,
  },
  cap: { alignItems: "center", paddingTop: 26, paddingHorizontal: 30 },
  eyebrow: { fontSize: 12, fontWeight: "800", letterSpacing: 1.5, color: colors.accent },
  h2: {
    fontSize: 23,
    fontWeight: "800",
    letterSpacing: -0.7,
    lineHeight: 32,
    color: colors.ink,
    textAlign: "center",
    marginTop: 12,
  },
  sub: {
    fontSize: 14,
    lineHeight: 21,
    color: colors.sec,
    marginTop: 10,
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
  dot: { width: 7, height: 7, borderRadius: 4, backgroundColor: colors.glassBorder },
  dotOn: { width: 22, backgroundColor: colors.accent },
  cta: {
    height: 52,
    borderRadius: 26,
    backgroundColor: colors.accent,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
  },
  ctaLabel: { fontSize: 16, fontWeight: "800", color: colors.onImage },
  aux: { textAlign: "center", fontSize: 13.5, fontWeight: "600", color: colors.sec },
});
