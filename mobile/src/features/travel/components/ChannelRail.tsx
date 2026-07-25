import { ScrollView, Pressable, View, Text, StyleSheet } from "react-native";
import { Icon } from "@/components/Icon";
import { SpotCard } from "@/features/travel/components/SpotCard";
import type { TravelSpot } from "@/features/travel/api";
import { colors, spacing } from "@/constants/theme";

const RAIL_LIMIT = 5;

interface Props {
  title: string;
  spots: TravelSpot[];
  notice?: string | null;
  onSeeAll: () => void;
}

export function ChannelRail({ title, spots, notice, onSeeAll }: Props) {
  if (!notice && spots.length === 0) return null;

  return (
    <View style={styles.section}>
      <View style={styles.head}>
        <Text style={styles.title}>{title}</Text>
        {!notice ? <Text style={styles.count}>{spots.length}</Text> : null}
        {!notice ? (
          <Pressable style={styles.all} hitSlop={8} onPress={onSeeAll} testID={`rail-all-${title}`}>
            <Text style={styles.allText}>전체</Text>
            <Icon name="chevron-right" size={14} color={colors.ter} strokeWidth={2} />
          </Pressable>
        ) : null}
      </View>

      {notice ? (
        <View style={styles.notice}>
          <Icon name="location" size={16} color={colors.ter} strokeWidth={1.9} />
          <Text style={styles.noticeText}>{notice}</Text>
        </View>
      ) : (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.rail}
        >
          {spots.slice(0, RAIL_LIMIT).map((spot) => (
            <SpotCard key={spot.contentId} spot={spot} />
          ))}
        </ScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  section: { marginTop: 26 },
  head: {
    flexDirection: "row",
    alignItems: "baseline",
    gap: 8,
    paddingHorizontal: spacing.lg,
    paddingBottom: 12,
  },
  title: { fontSize: 18, fontWeight: "800", letterSpacing: -0.4, color: colors.ink },
  count: { fontSize: 14, fontWeight: "800", color: colors.accentText },
  all: { marginLeft: "auto", flexDirection: "row", alignItems: "center", gap: 2 },
  allText: { fontSize: 12.5, fontWeight: "700", color: colors.ter },
  rail: { gap: 11, paddingHorizontal: spacing.lg, paddingBottom: 2 },
  notice: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginHorizontal: spacing.lg,
    paddingVertical: 14,
    paddingHorizontal: 14,
    borderRadius: 12,
    backgroundColor: colors.inset,
  },
  noticeText: { flex: 1, fontSize: 13, color: colors.sec },
});
