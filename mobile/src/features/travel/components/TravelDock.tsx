import { ScrollView, Pressable, View, Text, TextInput, StyleSheet } from "react-native";
import { Image } from "expo-image";
import { Icon } from "@/components/Icon";
import type { DockChip } from "@/features/travel/lib/dock-chips";
import type { PhotoUpload } from "@/features/travel/api";
import { colors, radii, spacing } from "@/constants/theme";

export const ATTACH_HEADLINE = "이 사진 같은 분위기로 찾아요";
export const ATTACH_NOTICE = "사진은 저장하지 않아요";
export const PHOTO_CHIP_LABEL = "사진";
export const PHOTO_CHIP_TEST_ID = "travel-chip-photo";
export const LOCATION_PRIMER_TEXT = "위치를 켜면 내 근처로 물어볼 수 있어요";
export const LOCATION_PRIMER_ACTION = "켜기";

const CHIP_GAP = 7;

interface Props {
  value: string;
  photo: PhotoUpload | null;
  chips: DockChip[];
  disabled: boolean;
  placeholder: string;
  locationAskable: boolean;
  bottom: number;
  onChange: (text: string) => void;
  onChipPress: (chip: DockChip) => void;
  onShoot: () => void;
  onClearAttach: () => void;
  onSubmit: () => void;
  onFocus: () => void;
  onAskLocation: () => void;
}

function chipLabel(chip: DockChip): string {
  if (chip.kind === "photo") return PHOTO_CHIP_LABEL;
  if (chip.kind === "context") return chip.expanded ? chip.title : `${chip.title} 근처`;
  return chip.chip.label;
}

function ChipButton({
  chip,
  testID,
  disabled,
  onPress,
}: {
  chip: DockChip;
  testID: string;
  disabled: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      testID={testID}
      accessibilityRole="button"
      accessibilityLabel={chipLabel(chip)}
      style={({ pressed }) => [
        dockStyles.chip,
        chip.kind === "context" && dockStyles.chipContext,
        (pressed || disabled) && dockStyles.pressed,
      ]}
      disabled={disabled}
      onPress={onPress}
    >
      {chip.kind === "photo" ? (
        <Icon name="image" size={15} color={colors.accentText} strokeWidth={1.9} />
      ) : null}
      {chip.kind === "context" ? (
        <Icon name="map-pin" size={14} color={colors.accentText} strokeWidth={1.9} />
      ) : null}
      <Text style={[dockStyles.chipText, chip.kind === "context" && dockStyles.chipTextContext]}>
        {chipLabel(chip)}
      </Text>
      {chip.kind === "context" && chip.expanded ? (
        <Icon name="close" size={12} color={colors.accentText} strokeWidth={2.4} />
      ) : null}
    </Pressable>
  );
}

export function TravelDock({
  value,
  photo,
  chips,
  disabled,
  placeholder,
  locationAskable,
  bottom,
  onChange,
  onChipPress,
  onShoot,
  onClearAttach,
  onSubmit,
  onFocus,
  onAskLocation,
}: Props) {
  const ready = !disabled && (value.trim().length > 0 || photo !== null);
  const pinnedChip = chips.find((chip) => chip.kind === "photo") ?? null;
  const scrollingChips = chips.filter((chip) => chip.kind !== "photo");

  return (
    <View style={[dockStyles.root, { bottom }]} pointerEvents="box-none">
      {locationAskable && photo === null ? (
        <Pressable
          testID="travel-ask-location"
          accessibilityRole="button"
          style={({ pressed }) => [dockStyles.primer, pressed && dockStyles.pressed]}
          onPress={onAskLocation}
        >
          <Icon name="location" size={15} color={colors.sec} strokeWidth={1.9} />
          <Text style={dockStyles.primerText}>{LOCATION_PRIMER_TEXT}</Text>
          <Text style={dockStyles.primerAction}>{LOCATION_PRIMER_ACTION}</Text>
        </Pressable>
      ) : null}

      {photo ? (
        <View style={dockStyles.attach} testID="travel-attach-banner">
          <Image source={{ uri: photo.uri }} style={dockStyles.attachThumb} contentFit="cover" />
          <View style={dockStyles.attachCopy}>
            <Text style={dockStyles.attachTitle}>{ATTACH_HEADLINE}</Text>
            <Text style={dockStyles.attachNote}>{ATTACH_NOTICE}</Text>
          </View>
          <Pressable
            testID="travel-attach-clear"
            accessibilityRole="button"
            accessibilityLabel="첨부 사진 제거"
            hitSlop={8}
            onPress={onClearAttach}
          >
            <Icon name="close" size={16} color={colors.ter} strokeWidth={2} />
          </Pressable>
        </View>
      ) : (
        <View style={dockStyles.chipBand} pointerEvents="box-none">
          {pinnedChip ? (
            <ChipButton
              chip={pinnedChip}
              testID={PHOTO_CHIP_TEST_ID}
              disabled={disabled}
              onPress={() => onChipPress(pinnedChip)}
            />
          ) : null}
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            keyboardShouldPersistTaps="handled"
            style={dockStyles.chipTrack}
            contentContainerStyle={dockStyles.chips}
          >
            {scrollingChips.map((chip, index) => (
              <ChipButton
                key={`${index}-${chip.kind}`}
                chip={chip}
                testID={`travel-chip-${index}`}
                disabled={disabled}
                onPress={() => onChipPress(chip)}
              />
            ))}
          </ScrollView>
        </View>
      )}

      <View style={dockStyles.field}>
        <Icon name="search" size={17} color={colors.ter} strokeWidth={1.9} />
        <TextInput
          testID="travel-input"
          style={dockStyles.input}
          value={value}
          onChangeText={onChange}
          onFocus={onFocus}
          placeholder={placeholder}
          placeholderTextColor={colors.ter}
          returnKeyType="send"
          onSubmitEditing={onSubmit}
          editable={!disabled}
        />
        <Pressable
          testID="travel-shoot"
          accessibilityRole="button"
          accessibilityLabel="사진 촬영"
          style={dockStyles.iconButton}
          hitSlop={4}
          onPress={onShoot}
          disabled={disabled}
        >
          <Icon name="camera" size={17} color={colors.sec} strokeWidth={1.9} />
        </Pressable>
        <Pressable
          testID="travel-send"
          accessibilityRole="button"
          accessibilityLabel="보내기"
          style={[dockStyles.send, ready && dockStyles.sendReady]}
          onPress={onSubmit}
          disabled={!ready}
        >
          <Icon
            name="arrow-up"
            size={17}
            color={ready ? colors.onImage : colors.ter}
            strokeWidth={2.3}
          />
        </Pressable>
      </View>
    </View>
  );
}

export const dockStyles = StyleSheet.create({
  root: {
    position: "absolute",
    left: 0,
    right: 0,
    paddingHorizontal: spacing.md,
    paddingBottom: 12,
  },
  pressed: { opacity: 0.7 },
  primer: {
    flexDirection: "row",
    alignItems: "center",
    gap: 9,
    height: 38,
    marginBottom: 9,
    paddingHorizontal: spacing.md,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.glassFill,
  },
  primerText: {
    flex: 1,
    fontSize: 12.5,
    fontWeight: "700",
    letterSpacing: -0.2,
    color: colors.sec,
  },
  primerAction: { fontSize: 11.5, fontWeight: "800", color: colors.accentText },
  attach: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    marginBottom: 9,
    paddingVertical: 8,
    paddingHorizontal: 10,
    borderRadius: 15,
    borderWidth: 1,
    borderColor: "rgba(255,59,83,0.32)",
    backgroundColor: colors.accentFill,
  },
  attachThumb: { width: 46, height: 46, borderRadius: 11 },
  attachCopy: { flex: 1 },
  attachTitle: { fontSize: 13.5, fontWeight: "700", letterSpacing: -0.2, color: colors.ink },
  attachNote: { marginTop: 3, fontSize: 11.5, color: colors.sec },
  chipBand: { flexDirection: "row", alignItems: "flex-start", gap: CHIP_GAP, marginBottom: 9 },
  chipTrack: { flexGrow: 0, flexShrink: 1 },
  chips: { gap: CHIP_GAP },
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
  chipContext: { borderColor: "rgba(255,59,83,0.38)", backgroundColor: colors.accentFill },
  chipText: { fontSize: 13, fontWeight: "600", letterSpacing: -0.2, color: colors.ink },
  chipTextContext: { color: colors.accentText, fontWeight: "700" },
  field: {
    flexDirection: "row",
    alignItems: "center",
    gap: 9,
    height: 46,
    paddingLeft: 13,
    paddingRight: 6,
    borderRadius: 13,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.raiseStrong,
  },
  input: {
    flex: 1,
    minWidth: 0,
    padding: 0,
    fontSize: 15,
    fontWeight: "600",
    letterSpacing: -0.2,
    color: colors.ink,
  },
  iconButton: { width: 30, height: 32, alignItems: "center", justifyContent: "center" },
  send: {
    width: 32,
    height: 32,
    borderRadius: radii.md,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.fillStrong,
  },
  sendReady: { backgroundColor: colors.accent },
});
