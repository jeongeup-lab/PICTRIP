import { View, Text, Pressable, StyleSheet } from "react-native";
import { RemoteImage } from "@/components/RemoteImage";
import { Icon } from "@/components/Icon";
import { subline } from "@/features/saved/lib/sort";
import type { SpotCard } from "@/lib/api-types";
import { colors, radii, spacing } from "@/constants/theme";

interface Props {
  spot: SpotCard;
  distance?: string | null;
  onPress: () => void;
  onPressIn?: () => void;
  testID?: string;
}

export function SavedListRow({ spot, distance, onPress, onPressIn, testID }: Props) {
  const sub = subline(spot);
  return (
    <Pressable
      accessibilityRole="button"
      style={({ pressed }) => [styles.row, pressed && styles.pressed]}
      onPress={onPress}
      onPressIn={onPressIn}
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
      {distance ? <Text style={styles.dist}>{distance}</Text> : null}
      <Icon name="chevron-right" size={17} color={colors.ter} />
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
    backgroundColor: colors.bg,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  pressed: { backgroundColor: colors.inset },
  thumb: { width: 54, height: 54, borderRadius: radii.md },
  main: { flex: 1, minWidth: 0 },
  title: { fontSize: 14.5, fontWeight: "700", letterSpacing: -0.2, color: colors.ink },
  sub: { marginTop: 3, fontSize: 12, color: colors.ter },
  dist: { fontSize: 12.5, fontWeight: "700", color: colors.sec },
});
