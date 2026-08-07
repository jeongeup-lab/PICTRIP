import { ScrollView, Pressable, View, Text, TextInput, StyleSheet } from "react-native";
import { Image } from "expo-image";
import { Icon } from "@/components/Icon";
import type { PhotoUpload } from "@/features/travel/api";
import type { Chip } from "@/features/travel/lib/chips";
import { colors, radii, spacing } from "@/constants/theme";

export const ATTACH_HEADLINE = "이 사진 같은 분위기로 찾아요";

export const ATTACH_NOTICE = "사진은 저장하지 않아요";

export const ASK_PLACEHOLDER = "어디로 갈지 말해보세요";

export const ATTACHED_PLACEHOLDER = "지역이나 조건을 덧붙여 보세요";

export const ANCHORED_PLACEHOLDER = "에 대해 물어보기";

interface Props {
  value: string;
  photo: PhotoUpload | null;
  chips: Chip[];
  disabled: boolean;
  anchorTitle?: string | null;
  onClearAnchor?: () => void;
  onChange: (text: string) => void;
  onSuggest: (chip: Chip) => void;
  onAttach: () => void;
  onShoot: () => void;
  onClearAttach: () => void;
  onSubmit: () => void;
  onFocus?: () => void;
}

function placeholderFor(photo: PhotoUpload | null, anchored: boolean): string {
  if (anchored) return ANCHORED_PLACEHOLDER;
  return photo ? ATTACHED_PLACEHOLDER : ASK_PLACEHOLDER;
}

export function AskComposer({
  value,
  photo,
  chips,
  disabled,
  anchorTitle = null,
  onClearAnchor,
  onChange,
  onSuggest,
  onAttach,
  onShoot,
  onClearAttach,
  onSubmit,
  onFocus,
}: Props) {
  const ready = !disabled && (value.trim().length > 0 || photo !== null);

  return (
    <View style={styles.root}>
      {photo ? (
        <View style={styles.attach} testID="travel-attach-banner">
          <Image source={{ uri: photo.uri }} style={styles.attachThumb} contentFit="cover" />
          <View style={styles.attachCopy}>
            <Text style={styles.attachTitle}>{ATTACH_HEADLINE}</Text>
            <Text style={styles.attachNote}>{ATTACH_NOTICE}</Text>
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

      <View style={[styles.field, anchorTitle ? styles.fieldAnchored : null]}>
        {anchorTitle ? (
          <View style={styles.token} testID="travel-anchor-banner">
            <Text style={styles.tokenText} numberOfLines={1}>
              {anchorTitle}
            </Text>
            <Pressable
              testID="travel-anchor-clear"
              accessibilityRole="button"
              accessibilityLabel="선택 해제"
              hitSlop={8}
              onPress={onClearAnchor}
            >
              <Icon name="close" size={11} color={colors.accentText} strokeWidth={2.6} />
            </Pressable>
          </View>
        ) : (
          <Icon name="search" size={17} color={colors.ter} strokeWidth={1.9} />
        )}

        <TextInput
          testID="travel-input"
          style={styles.input}
          value={value}
          onChangeText={onChange}
          onFocus={onFocus}
          placeholder={placeholderFor(photo, anchorTitle !== null)}
          placeholderTextColor={colors.ter}
          returnKeyType="send"
          onSubmitEditing={onSubmit}
          editable={!disabled}
        />

        <Pressable
          testID="travel-shoot"
          accessibilityRole="button"
          accessibilityLabel="사진 촬영"
          style={styles.iconButton}
          hitSlop={4}
          onPress={onShoot}
          disabled={disabled}
        >
          <Icon name="camera" size={17} color={colors.sec} strokeWidth={1.9} />
        </Pressable>
        <Pressable
          testID="travel-attach"
          accessibilityRole="button"
          accessibilityLabel="사진 올리기"
          style={styles.iconButton}
          hitSlop={4}
          onPress={onAttach}
          disabled={disabled}
        >
          <Icon name="image" size={17} color={colors.sec} strokeWidth={1.9} />
        </Pressable>
        <Pressable
          testID="travel-send"
          accessibilityRole="button"
          accessibilityLabel="보내기"
          style={[styles.send, ready && styles.sendReady]}
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

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.chips}
        keyboardShouldPersistTaps="handled"
      >
        {chips.map((chip) => (
          <Pressable
            key={chip.label}
            testID={`travel-chip-${chip.label}`}
            accessibilityRole="button"
            style={({ pressed }) => [
              styles.chip,
              chip.kind === "anchor" && styles.chipOn,
              pressed && styles.chipPressed,
            ]}
            onPress={() => onSuggest(chip)}
          >
            <Text style={[styles.chipText, chip.kind === "anchor" && styles.chipTextOn]}>
              {chip.label}
            </Text>
          </Pressable>
        ))}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { paddingTop: 4 },
  attach: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    marginHorizontal: spacing.md,
    marginBottom: 8,
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
    marginHorizontal: spacing.md,
    height: 46,
    paddingLeft: 13,
    paddingRight: 6,
    borderRadius: 13,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.raiseStrong,
  },
  fieldAnchored: { borderColor: "rgba(255,59,83,0.5)" },
  token: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    maxWidth: "52%",
    paddingVertical: 4,
    paddingHorizontal: 8,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: "rgba(255,59,83,0.4)",
    backgroundColor: colors.accentFill,
  },
  tokenText: { flexShrink: 1, fontSize: 12, fontWeight: "700", color: colors.accentText },
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
  chips: { gap: 7, paddingHorizontal: spacing.md, paddingTop: 12, paddingBottom: 2 },
  chip: {
    height: 33,
    paddingHorizontal: 14,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.raiseStrong,
    flexDirection: "row",
    alignItems: "center",
  },
  chipOn: { backgroundColor: colors.accent, borderColor: colors.accent },
  chipPressed: { opacity: 0.7 },
  chipText: { fontSize: 13, fontWeight: "600", letterSpacing: -0.2, color: colors.ink },
  chipTextOn: { color: colors.onImage },
});
