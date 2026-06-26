import { View, Text, Pressable, ScrollView, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router } from "expo-router";
import { Icon } from "@/components/Icon";
import { Skeleton } from "@/components/Skeleton";
import { SavedCard } from "@/features/saved/components/SavedCard";
import { useSavedList, useUnsaveMutation } from "@/features/saved/queries";
import { prefetchSpot } from "@/features/spots/queries";
import { colors, spacing } from "@/constants/theme";

export default function SavedScreen() {
  const insets = useSafeAreaInsets();
  const { data, isLoading } = useSavedList();
  const unsave = useUnsaveMutation();

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <View style={styles.nav}>
        <Pressable style={styles.navBtn} onPress={() => router.back()} hitSlop={8}>
          <Icon name="chevron-left" size={23} />
        </Pressable>
        <Text style={styles.title}>스크랩</Text>
      </View>

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.grid}>
        {isLoading ? (
          [0, 1, 2, 3].map((i) => <Skeleton key={i} height={150} width="48.5%" radius={14} />)
        ) : data && data.length > 0 ? (
          data.map((spot) => (
            <SavedCard
              key={spot.contentId}
              spot={spot}
              onPressIn={() => prefetchSpot(spot.contentId)}
              onPress={() => router.push(`/spots/${spot.contentId}`)}
              onUnsave={() => unsave.mutate(spot.contentId)}
            />
          ))
        ) : (
          <Text style={styles.empty}>아직 스크랩한 곳이 없어요</Text>
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  nav: {
    height: 50,
    flexDirection: "row",
    alignItems: "center",
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  navBtn: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
  title: {
    position: "absolute",
    left: 0,
    right: 0,
    textAlign: "center",
    fontSize: 17,
    fontWeight: "700",
    color: colors.ink,
  },
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "space-between",
    rowGap: 12,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.xxl,
  },
  empty: {
    width: "100%",
    textAlign: "center",
    color: colors.ter,
    fontSize: 14,
    marginTop: spacing.xxl,
  },
});
