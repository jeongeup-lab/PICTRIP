import { ScrollView, Pressable, View, Text, StyleSheet } from "react-native";
import { Icon } from "@/components/Icon";
import { SpotCard } from "@/features/travel/components/SpotCard";
import { PhotoStartCard } from "@/features/travel/components/PhotoStartCard";
import { boardPinHeight, splitBoardColumns } from "@/features/travel/lib/board";
import type { TravelSpot } from "@/features/travel/api";
import { colors, spacing } from "@/constants/theme";

export type BoardFilter = "all" | "hot" | "hidden" | "around";

export const BOARD_FILTERS: { key: BoardFilter; label: string }[] = [
  { key: "all", label: "전체" },
  { key: "hot", label: "인기" },
  { key: "hidden", label: "숨은 곳" },
  { key: "around", label: "내 근처" },
];

const GAP = 9;

type Cell = { key: string; height: number; spot: TravelSpot | null };

interface Props {
  filter: BoardFilter;
  spots: TravelSpot[];
  notice: string | null;
  onFilter: (filter: BoardFilter) => void;
  onPhotoStart: () => void;
}

export function PinBoard({ filter, spots, notice, onFilter, onPhotoStart }: Props) {
  const cells: Cell[] = [
    { key: "photo-start", height: boardPinHeight(0), spot: null },
    ...spots.map((spot, index) => ({
      key: spot.contentId,
      height: boardPinHeight(index + 1),
      spot,
    })),
  ];
  const columns = splitBoardColumns(cells);

  return (
    <View style={styles.section}>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.chips}
      >
        {BOARD_FILTERS.map(({ key, label }) => {
          const active = key === filter;
          return (
            <Pressable
              key={key}
              testID={`board-filter-${key}`}
              accessibilityRole="button"
              accessibilityState={{ selected: active }}
              style={[styles.chip, active && styles.chipActive]}
              onPress={() => onFilter(key)}
            >
              <Text style={[styles.chipText, active && styles.chipTextActive]}>{label}</Text>
            </Pressable>
          );
        })}
      </ScrollView>

      {notice ? (
        <View style={styles.notice}>
          <Icon name="location" size={16} color={colors.ter} strokeWidth={1.9} />
          <Text style={styles.noticeText}>{notice}</Text>
        </View>
      ) : null}

      <View style={styles.board}>
        {columns.map((column, columnIndex) => (
          <View key={columnIndex === 0 ? "left" : "right"} style={styles.column}>
            {column.map((cell) =>
              cell.spot ? (
                <SpotCard
                  key={cell.key}
                  spot={cell.spot}
                  style={{ width: "100%", height: cell.height }}
                />
              ) : (
                <PhotoStartCard
                  key={cell.key}
                  style={{ minHeight: cell.height }}
                  onPress={onPhotoStart}
                />
              ),
            )}
          </View>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  section: { marginTop: spacing.lg },
  chips: { gap: 7, paddingHorizontal: spacing.lg, paddingVertical: 2 },
  chip: {
    height: 34,
    paddingHorizontal: 14,
    borderRadius: 999,
    justifyContent: "center",
    backgroundColor: colors.fill,
  },
  chipActive: { backgroundColor: colors.ink },
  chipText: { fontSize: 12.5, fontWeight: "800", letterSpacing: -0.2, color: colors.sec },
  chipTextActive: { color: colors.onImage },
  notice: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginTop: GAP + 3,
    marginHorizontal: spacing.lg,
    paddingVertical: 14,
    paddingHorizontal: 14,
    borderRadius: 12,
    backgroundColor: colors.inset,
  },
  noticeText: { flex: 1, fontSize: 13, color: colors.sec },
  board: {
    flexDirection: "row",
    gap: GAP,
    marginTop: GAP + 3,
    paddingHorizontal: spacing.lg,
  },
  column: { flex: 1, gap: GAP },
});
