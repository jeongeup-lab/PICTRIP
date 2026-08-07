import { View, Text, Pressable, StyleSheet } from "react-native";
import { RemoteImage } from "@/components/RemoteImage";
import { Icon } from "@/components/Icon";
import { subline } from "@/features/saved/lib/sort";
import { useSaveOptimistic } from "@/features/saved/hooks/use-save-optimistic";
import type { SpotCard } from "@/lib/api-types";
import { colors, radii, spacing } from "@/constants/theme";

interface Props {
  spot: SpotCard;
  onPress: () => void;
  testID?: string;
}

export function RecentSpotRow({ spot, onPress, testID }: Props) {
  const { saved, toggle } = useSaveOptimistic(spot.contentId);
  const sub = subline(spot);

  return (
    <Pressable
      accessibilityRole="button"
      style={({ pressed }) => [styles.row, pressed && styles.pressed]}
      onPress={onPress}
      testID={testID}
    >
      <RemoteImage uri={spot.firstImageUrl} style={styles.thumb} radius={radii.md} />
      <View style={styles.main}>
        <Text style={styles.title} numberOfLines={1}>
          {spot.title}
        </Text>
        {sub ? (
          <Text style={styles.sub} numberOfLines={1}>
            {sub}
          </Text>
        ) : null}
      </View>
      <Pressable
        accessibilityRole="button"
        hitSlop={10}
        onPress={() => void toggle()}
        style={styles.heart}
        testID={testID ? `${testID}-heart` : undefined}
      >
        <Icon
          name={saved ? "heart-fill" : "heart"}
          size={19}
          color={saved ? colors.accent : colors.ter}
        />
      </Pressable>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingVertical: 10,
    paddingHorizontal: spacing.md,
  },
  pressed: { backgroundColor: colors.fill },
  thumb: { width: 48, height: 48, borderRadius: radii.md },
  main: { flex: 1, minWidth: 0 },
  title: { fontSize: 14, fontWeight: "700", letterSpacing: -0.2, color: colors.ink },
  sub: { marginTop: 3, fontSize: 12, color: colors.ter },
  heart: { width: 34, height: 34, alignItems: "center", justifyContent: "center" },
});
