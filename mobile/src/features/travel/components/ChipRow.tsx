import { ScrollView, Pressable, View, Text, StyleSheet } from "react-native";
import { Icon } from "@/components/Icon";
import type { DockChip } from "@/features/travel/lib/dock-chips";
import { colors, radii, spacing } from "@/constants/theme";

export const PHOTO_CHIP_LABEL = "사진";
export const PHOTO_CHIP_TEST_ID = "travel-chip-photo";

const CHIP_GAP = 7;

interface Props {
  chips: DockChip[];
  disabled: boolean;
  inset: boolean;
  opaque?: boolean;
  onChipPress: (chip: DockChip) => void;
}

export function chipLabel(chip: DockChip): string {
  return chip.kind === "photo" ? PHOTO_CHIP_LABEL : chip.chip.label;
}

function ChipButton({
  chip,
  testID,
  disabled,
  opaque,
  onPress,
}: {
  chip: DockChip;
  testID: string;
  disabled: boolean;
  opaque: boolean;
  onPress: () => void;
}) {
  const photo = chip.kind === "photo";
  return (
    <Pressable
      testID={testID}
      accessibilityRole="button"
      accessibilityLabel={chipLabel(chip)}
      style={({ pressed }) => [
        chipStyles.chip,
        opaque && chipStyles.chipOpaque,
        photo && chipStyles.chipPhoto,
        (pressed || disabled) && chipStyles.pressed,
      ]}
      disabled={disabled}
      onPress={onPress}
    >
      {photo ? <Icon name="image" size={15} color={colors.accentText} strokeWidth={1.9} /> : null}
      <Text style={[chipStyles.chipText, photo && chipStyles.chipTextPhoto]}>
        {chipLabel(chip)}
      </Text>
    </Pressable>
  );
}

export function ChipRow({ chips, disabled, inset, opaque = false, onChipPress }: Props) {
  if (chips.length === 0) return null;

  const pinned = chips.find((chip) => chip.kind === "photo") ?? null;
  const scrolling = chips.filter((chip) => chip.kind !== "photo");

  return (
    <View
      testID="travel-chip-row"
      style={[chipStyles.band, inset && chipStyles.bandInset]}
      pointerEvents="box-none"
    >
      {pinned ? (
        <ChipButton
          chip={pinned}
          testID={PHOTO_CHIP_TEST_ID}
          disabled={disabled}
          opaque={opaque}
          onPress={() => onChipPress(pinned)}
        />
      ) : null}
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
        style={chipStyles.track}
        contentContainerStyle={chipStyles.chips}
      >
        {scrolling.map((chip, index) => (
          <ChipButton
            key={`${index}-${chipLabel(chip)}`}
            chip={chip}
            testID={`travel-chip-${index}`}
            disabled={disabled}
            opaque={opaque}
            onPress={() => onChipPress(chip)}
          />
        ))}
      </ScrollView>
    </View>
  );
}

export const chipStyles = StyleSheet.create({
  band: { flexDirection: "row", alignItems: "flex-start", gap: CHIP_GAP },
  bandInset: { paddingHorizontal: spacing.md },
  track: { flexGrow: 0, flexShrink: 1 },
  chips: { gap: CHIP_GAP },
  pressed: { opacity: 0.7 },
  chip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    height: 33,
    paddingHorizontal: 14,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.raiseStrong,
  },
  chipOpaque: { backgroundColor: colors.inset },
  chipPhoto: { borderColor: "rgba(255,59,83,0.38)", backgroundColor: colors.accentFill },
  chipText: { fontSize: 13, fontWeight: "600", letterSpacing: -0.2, color: colors.ink },
  chipTextPhoto: { color: colors.accentText, fontWeight: "700" },
});
