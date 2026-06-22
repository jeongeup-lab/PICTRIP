import { View, Text, Pressable, Linking, StyleSheet } from "react-native";
import type { SpotDetail } from "@/lib/api-types";
import { colors, spacing } from "@/constants/theme";

function Row({ label, value, onPress }: { label: string; value: string; onPress?: () => void }) {
  return (
    <Pressable onPress={onPress} disabled={!onPress} style={styles.row}>
      <Text style={styles.label}>{label}</Text>
      <Text style={styles.value} numberOfLines={2}>
        {value}
      </Text>
    </Pressable>
  );
}

export function LocationSection({ spot }: { spot: SpotDetail }) {
  const address = [spot.addr1, spot.addr2].filter(Boolean).join(" ");
  return (
    <View style={styles.section}>
      {address ? <Row label="주소" value={address} /> : null}
      {spot.intro?.usetime ? <Row label="이용시간" value={spot.intro.usetime} /> : null}
      {spot.tel ? (
        <Row label="전화" value={spot.tel} onPress={() => Linking.openURL(`tel:${spot.tel}`)} />
      ) : null}
      {spot.homepage ? (
        <Row
          label="홈페이지"
          value={spot.homepage}
          onPress={() => Linking.openURL(spot.homepage as string)}
        />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  section: { paddingHorizontal: spacing.lg, marginTop: spacing.xl, gap: spacing.sm },
  row: { flexDirection: "row", gap: spacing.md },
  label: { width: 64, fontSize: 14, color: colors.ter },
  value: { flex: 1, fontSize: 14, color: colors.ink },
});
