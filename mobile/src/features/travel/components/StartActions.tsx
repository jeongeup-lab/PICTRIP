import { Pressable, View, Text, StyleSheet } from "react-native";
import { Icon } from "@/components/Icon";
import { colors, spacing } from "@/constants/theme";

export const LOCATION_PRIMER_TEXT = "위치를 켜면 내 근처로 물어볼 수 있어요";
export const LOCATION_PRIMER_ACTION = "켜기";

interface Props {
  onAskLocation?: () => void;
  locationAskable?: boolean;
}

export function StartActions({ onAskLocation, locationAskable = false }: Props) {
  if (!locationAskable) return null;

  return (
    <View style={styles.root}>
      <Pressable
        testID="travel-start-location"
        accessibilityRole="button"
        style={({ pressed }) => [styles.primer, pressed && styles.primerPressed]}
        onPress={onAskLocation}
      >
        <Icon name="location" size={15} color={colors.sec} strokeWidth={1.9} />
        <Text style={styles.primerText}>{LOCATION_PRIMER_TEXT}</Text>
        <Text style={styles.primerAction}>{LOCATION_PRIMER_ACTION}</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { width: "100%", maxWidth: 320, marginTop: 26 },
  primer: {
    flexDirection: "row",
    alignItems: "center",
    gap: 9,
    paddingVertical: 11,
    paddingHorizontal: spacing.md,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.inset,
  },
  primerPressed: { backgroundColor: colors.fill },
  primerText: {
    flex: 1,
    fontSize: 12.5,
    fontWeight: "700",
    letterSpacing: -0.2,
    color: colors.sec,
  },
  primerAction: { fontSize: 11.5, fontWeight: "800", color: colors.accentText },
});
