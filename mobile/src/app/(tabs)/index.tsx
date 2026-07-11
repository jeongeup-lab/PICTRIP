import { ScrollView, View, Text, Pressable, RefreshControl, StyleSheet } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router } from "expo-router";
import { useHomeFeed } from "@/features/feed/queries";
import { HeroCarousel } from "@/features/feed/components/HeroCarousel";
import { MoodRail } from "@/features/feed/components/MoodRail";
import { Skeleton } from "@/components/Skeleton";
import { PrimaryButton } from "@/components/PrimaryButton";
import { colors, spacing } from "@/constants/theme";

export default function HomeScreen() {
  const { data, isLoading, isError, isRefetching, refetch } = useHomeFeed();

  // Backend drops unresolvable heroes and thin rails — both can come back empty.
  const isEmpty = !!data && data.heroes.length === 0 && data.rails.length === 0;

  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      <View style={styles.bar}>
        <View style={styles.wordmarkRow}>
          <Text style={styles.wordmark}>PICTRIP</Text>
          <View style={styles.wordmarkDot} />
        </View>
      </View>

      {isLoading ? (
        <View style={styles.loading}>
          <Skeleton height={280} radius={12} />
          <Skeleton height={20} width="40%" style={{ marginTop: spacing.xxl }} />
          <Skeleton height={140} style={{ marginTop: spacing.md }} />
        </View>
      ) : isError || !data ? (
        <View style={styles.error}>
          <Text style={styles.errorText}>피드를 불러오지 못했어요.</Text>
          <PrimaryButton label="다시 시도" onPress={() => refetch()} />
        </View>
      ) : (
        <ScrollView
          showsVerticalScrollIndicator={false}
          contentContainerStyle={isEmpty ? styles.emptyGrow : undefined}
          refreshControl={
            <RefreshControl
              refreshing={isRefetching}
              onRefresh={() => void refetch()}
              tintColor={colors.ter}
            />
          }
        >
          {isEmpty ? (
            <View style={styles.empty}>
              <Text style={styles.emptyText}>곧 새로운 큐레이션을 준비할게요</Text>
            </View>
          ) : (
            <>
              {data.heroes.length > 0 ? (
                <View style={{ paddingTop: spacing.md }}>
                  <HeroCarousel heroes={data.heroes} />
                </View>
              ) : null}
              {data.rails.map((rail, i) => (
                <View key={rail.id}>
                  {i > 0 ? <View style={styles.band} /> : null}
                  <MoodRail rail={rail} />
                </View>
              ))}
            </>
          )}

          <View style={styles.footer}>
            <View style={styles.footerLinks}>
              <Pressable
                testID="footer-terms"
                accessibilityRole="link"
                hitSlop={8}
                onPress={() => router.push("/legal/terms")}
              >
                <Text style={styles.footerLink}>이용약관</Text>
              </Pressable>
              <View style={styles.footerSep} />
              <Pressable
                testID="footer-privacy"
                accessibilityRole="link"
                hitSlop={8}
                onPress={() => router.push("/legal/privacy")}
              >
                <Text style={styles.footerLinkStrong}>개인정보처리방침</Text>
              </Pressable>
              <View style={styles.footerSep} />
              <Pressable
                testID="footer-data-source"
                accessibilityRole="link"
                hitSlop={8}
                onPress={() => router.push("/legal/data-sources")}
              >
                <Text style={styles.footerLink}>데이터 출처</Text>
              </Pressable>
            </View>
            <Text style={styles.footerNote}>ⓒ PicTrip</Text>
          </View>
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  bar: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    alignItems: "center",
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  wordmarkRow: { flexDirection: "row", alignItems: "flex-end" },
  wordmark: { fontSize: 20, fontWeight: "800", letterSpacing: -0.5, color: colors.ink },
  wordmarkDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    marginLeft: 3,
    marginBottom: 4,
    backgroundColor: colors.accent,
  },
  loading: { padding: spacing.lg },
  error: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.md,
    padding: spacing.xl,
  },
  errorText: { fontSize: 15, color: colors.sec },
  emptyGrow: { flexGrow: 1 },
  empty: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: spacing.xl,
  },
  emptyText: { fontSize: 15, color: colors.sec },
  band: {
    height: 8,
    backgroundColor: colors.inset,
    borderTopWidth: 1,
    borderBottomWidth: 1,
    borderColor: colors.fill,
  },
  footer: {
    backgroundColor: colors.inset,
    borderTopWidth: 1,
    borderTopColor: colors.line,
    paddingVertical: spacing.lg,
    paddingHorizontal: spacing.lg,
    gap: spacing.sm,
  },
  footerLinks: { flexDirection: "row", alignItems: "center", gap: 12 },
  footerLink: { fontSize: 12, fontWeight: "600", color: colors.sec },
  footerLinkStrong: { fontSize: 12, fontWeight: "700", color: colors.ink },
  footerSep: { width: 1, height: 10, backgroundColor: colors.line },
  footerNote: { fontSize: 11.5, lineHeight: 17, color: colors.ter },
});
