import { Pressable, View, Text, StyleSheet } from "react-native";
import { Icon, type IconName } from "@/components/Icon";
import { colors, radii, spacing } from "@/constants/theme";

export const LOCATION_PRIMER_TEXT = "위치를 켜면 내 근처로 물어볼 수 있어요";
export const LOCATION_PRIMER_ACTION = "켜기";

export const PHOTO_ACTION = "사진으로";
export const NEARBY_ACTION = "내 근처";
export const FESTIVAL_ACTION = "축제";
export const SAVED_ACTION = "저장함";

interface Props {
  onPhoto: () => void;
  onNearby: () => void;
  onFestival: () => void;
  onSaved: () => void;
  nearbyEnabled?: boolean;
  onAskLocation?: () => void;
  locationAskable?: boolean;
}

interface QuickAction {
  testID: string;
  icon: IconName;
  label: string;
  onPress: () => void;
  primary?: boolean;
}

function Quick({ testID, icon, label, onPress, primary = false }: QuickAction) {
  return (
    <Pressable
      testID={testID}
      accessibilityRole="button"
      accessibilityLabel={label}
      style={({ pressed }) => [styles.quick, pressed && styles.pressed]}
      onPress={onPress}
    >
      <View style={[styles.tile, primary && styles.tilePrimary]}>
        <Icon
          name={icon}
          size={21}
          color={primary ? colors.onImage : colors.ink}
          strokeWidth={1.9}
        />
      </View>
      <Text style={styles.quickLabel} numberOfLines={1}>
        {label}
      </Text>
    </Pressable>
  );
}

export function StartActions({
  onPhoto,
  onNearby,
  onFestival,
  onSaved,
  nearbyEnabled = false,
  onAskLocation,
  locationAskable = false,
}: Props) {
  return (
    <View style={styles.root}>
      <View style={styles.grid}>
        <Quick
          testID="travel-quick-photo"
          icon="camera"
          label={PHOTO_ACTION}
          onPress={onPhoto}
          primary
        />
        {nearbyEnabled ? (
          <Quick testID="travel-nearby" icon="map-pin" label={NEARBY_ACTION} onPress={onNearby} />
        ) : null}
        <Quick
          testID="travel-quick-festival"
          icon="calendar"
          label={FESTIVAL_ACTION}
          onPress={onFestival}
        />
        <Quick
          testID="travel-quick-saved"
          icon="heart-fill"
          label={SAVED_ACTION}
          onPress={onSaved}
        />
      </View>

      {locationAskable ? (
        <Pressable
          testID="travel-start-location"
          accessibilityRole="button"
          style={({ pressed }) => [styles.primer, pressed && styles.pressed]}
          onPress={onAskLocation}
        >
          <Icon name="location" size={15} color={colors.sec} strokeWidth={1.9} />
          <Text style={styles.primerText}>{LOCATION_PRIMER_TEXT}</Text>
          <Text style={styles.primerAction}>{LOCATION_PRIMER_ACTION}</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { paddingHorizontal: spacing.md, paddingTop: 14 },
  grid: { flexDirection: "row", gap: 9 },
  quick: { flex: 1, alignItems: "center", gap: 8 },
  pressed: { opacity: 0.7 },
  tile: {
    width: 50,
    height: 50,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.raiseStrong,
    alignItems: "center",
    justifyContent: "center",
  },
  tilePrimary: { backgroundColor: colors.accent, borderColor: colors.accent },
  quickLabel: { fontSize: 11, fontWeight: "600", letterSpacing: -0.2, color: colors.sec },
  primer: {
    flexDirection: "row",
    alignItems: "center",
    gap: 9,
    marginTop: 16,
    paddingVertical: 11,
    paddingHorizontal: spacing.md,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.raise,
  },
  primerText: {
    flex: 1,
    fontSize: 12.5,
    fontWeight: "700",
    letterSpacing: -0.2,
    color: colors.sec,
  },
  primerAction: { fontSize: 11.5, fontWeight: "800", color: colors.accentText },
});
