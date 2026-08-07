import { View, Text, Pressable, StyleSheet } from "react-native";
import { Icon, type IconName } from "@/components/Icon";
import type { ProfileStats } from "@/features/profile/lib/stats";
import { colors, radii, spacing } from "@/constants/theme";

interface Props {
  stats: ProfileStats | null;
  onPressSaved?: () => void;
}

interface Tile {
  key: keyof ProfileStats;
  label: string;
  icon: IconName;
  accent?: boolean;
}

const TILES: readonly Tile[] = [
  { key: "saved", label: "스크랩", icon: "heart-fill", accent: true },
  { key: "regions", label: "지역", icon: "map-pin" },
  { key: "days", label: "함께한 날", icon: "calendar" },
] as const;

export function StatTiles({ stats, onPressSaved }: Props) {
  return (
    <View style={[styles.row, stats === null && styles.dim]} testID="stat-tiles">
      {TILES.map((tile) => {
        const value = stats === null ? "—" : String(stats[tile.key]);
        const onPress = tile.key === "saved" && stats !== null ? onPressSaved : undefined;
        return (
          <Pressable
            key={tile.key}
            accessibilityRole={onPress ? "button" : undefined}
            disabled={!onPress}
            onPress={onPress}
            style={styles.tile}
            testID={`stat-${tile.key}`}
          >
            <Icon
              name={tile.icon}
              size={19}
              color={tile.accent ? colors.accent : colors.ink}
              strokeWidth={1.8}
            />
            <Text style={styles.value}>{value}</Text>
            <Text style={styles.label}>{tile.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", gap: 8, paddingHorizontal: spacing.md, paddingTop: spacing.sm + 2 },
  dim: { opacity: 0.45 },
  tile: {
    flex: 1,
    alignItems: "center",
    gap: 7,
    paddingVertical: 13,
    borderRadius: radii.lg + 3,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.raise,
  },
  value: { fontSize: 16, fontWeight: "800", letterSpacing: -0.3, color: colors.ink },
  label: { fontSize: 11, fontWeight: "700", color: colors.sec },
});
