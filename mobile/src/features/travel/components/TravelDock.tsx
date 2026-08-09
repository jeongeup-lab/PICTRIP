import { Pressable, View, Text, TextInput, StyleSheet } from "react-native";
import { Image } from "expo-image";
import { Icon } from "@/components/Icon";
import type { PhotoUpload } from "@/features/travel/api";
import { colors, radii, spacing } from "@/constants/theme";

export const ATTACH_HEADLINE = "이 사진 같은 분위기로 찾아요";
export const ATTACH_NOTICE = "사진은 저장하지 않아요";
export const LOCATION_PRIMER_TEXT = "위치를 켜면 내 근처로 물어볼 수 있어요";
export const LOCATION_PRIMER_ACTION = "켜기";

interface Props {
  value: string;
  photo: PhotoUpload | null;
  disabled: boolean;
  placeholder: string;
  locationAskable: boolean;
  onChange: (text: string) => void;
  onFocus: () => void;
  onShoot: () => void;
  onClearAttach: () => void;
  onSubmit: () => void;
  onAskLocation: () => void;
}

export function TravelDock({
  value,
  photo,
  disabled,
  placeholder,
  locationAskable,
  onChange,
  onFocus,
  onShoot,
  onClearAttach,
  onSubmit,
  onAskLocation,
}: Props) {
  const ready = !disabled && (value.trim().length > 0 || photo !== null);

  return (
    <View style={dockStyles.root} pointerEvents="box-none">
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
      ) : null}

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
