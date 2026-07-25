import { Pressable, ScrollView, View, Text, StyleSheet } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router } from "expo-router";
import { Icon } from "@/components/Icon";
import { SpotCard, GRID_CARD_HEIGHT } from "@/features/travel/components/SpotCard";
import { useResults } from "@/features/travel/stores/results-store";
import { colors, spacing } from "@/constants/theme";

export default function TravelResultsScreen() {
  const title = useResults((s) => s.title);
  const spots = useResults((s) => s.spots);

  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      <View style={styles.nav}>
        <Pressable
          testID="results-back"
          style={styles.back}
          hitSlop={8}
          onPress={() => router.back()}
        >
          <Icon name="chevron-left" size={20} color={colors.ink} strokeWidth={2} />
        </Pressable>
        <View style={styles.navText}>
          <Text style={styles.navTitle} numberOfLines={1}>
            {title}
          </Text>
          <Text style={styles.navSub}>{spots.length}곳</Text>
        </View>
      </View>

      <ScrollView contentContainerStyle={styles.body} showsVerticalScrollIndicator={false}>
        <View style={styles.grid}>
          {spots.map((spot) => (
            <SpotCard key={spot.contentId} spot={spot} style={styles.gridCard} />
          ))}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  nav: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingVertical: 10,
    paddingHorizontal: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  back: { width: 36, height: 36, alignItems: "center", justifyContent: "center" },
  navText: { flex: 1 },
  navTitle: { fontSize: 16, fontWeight: "800", letterSpacing: -0.4, color: colors.ink },
  navSub: { marginTop: 2, fontSize: 12, color: colors.ter },
  body: { paddingTop: spacing.md + 2, paddingHorizontal: spacing.lg, paddingBottom: 40 },
  grid: { flexDirection: "row", flexWrap: "wrap", justifyContent: "space-between", rowGap: 16 },
  gridCard: { width: "48%", height: GRID_CARD_HEIGHT },
});
