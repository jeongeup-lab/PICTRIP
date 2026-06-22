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
import { PrimaryButton } from "@/components/PrimaryButton";
import { colors, spacing } from "@/constants/theme";

const SLIDES = [
  {
    title: "사진으로 떠나는\n여행",
    body: "마음에 든 장면을 올리면\n닮은 국내 여행지를 찾아드려요.",
  },
  { title: "지금 이 순간\n가까운 곳", body: "내 주변의 숨은 명소를\n혼잡도까지 한눈에." },
  { title: "마음에 들면\n스크랩", body: "좋았던 장소를 저장하고\n언제든 다시 꺼내보세요." },
];

export default function Onboarding() {
  const { width } = useWindowDimensions();
  const [index, setIndex] = useState(0);
  const scrollRef = useRef<ScrollView>(null);

  const onScroll = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    setIndex(Math.round(e.nativeEvent.contentOffset.x / width));
  };

  const finish = async (href: "/(tabs)" | "/onboarding-photo") => {
    await setOnboardingSeen();
    // P1: route to home. (Photo-first CTA wires to photo stack in P2.)
    router.replace("/(tabs)");
  };

  return (
    <SafeAreaView style={styles.root}>
      <Pressable style={styles.skip} onPress={() => finish("/(tabs)")} hitSlop={8}>
        <Text style={styles.skipText}>건너뛰기</Text>
      </Pressable>

      <ScrollView
        ref={scrollRef}
        horizontal
        pagingEnabled
        showsHorizontalScrollIndicator={false}
        onMomentumScrollEnd={onScroll}
        style={styles.pager}
      >
        {SLIDES.map((s) => (
          <View key={s.title} style={[styles.slide, { width }]}>
            <Text style={styles.title}>{s.title}</Text>
            <Text style={styles.body}>{s.body}</Text>
          </View>
        ))}
      </ScrollView>

      <View style={styles.dots}>
        {SLIDES.map((s, i) => (
          <View
            key={s.title}
            style={[styles.dot, { backgroundColor: i === index ? colors.ink : colors.line }]}
          />
        ))}
      </View>

      <View style={styles.cta}>
        <PrimaryButton label="사진으로 시작하기" onPress={() => finish("/(tabs)")} />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  skip: { alignSelf: "flex-end", padding: spacing.lg },
  skipText: { color: colors.ter, fontSize: 14, fontWeight: "600" },
  pager: { flex: 1 },
  slide: { flex: 1, justifyContent: "center", paddingHorizontal: spacing.xl, gap: spacing.md },
  title: {
    fontSize: 32,
    fontWeight: "800",
    letterSpacing: -0.6,
    color: colors.ink,
    lineHeight: 40,
  },
  body: { fontSize: 16, color: colors.sec, lineHeight: 24 },
  dots: { flexDirection: "row", justifyContent: "center", gap: 7, paddingVertical: spacing.lg },
  dot: { width: 7, height: 7, borderRadius: 4 },
  cta: { paddingHorizontal: spacing.xl, paddingBottom: spacing.xl },
});
