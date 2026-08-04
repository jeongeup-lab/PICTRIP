import { ScrollView, Pressable, View, Text, TextInput, StyleSheet } from "react-native";
import { Image } from "expo-image";
import { Icon } from "@/components/Icon";
import type { PhotoUpload } from "@/features/travel/api";
import { NEARBY_CHIP, type Chip } from "@/features/travel/lib/chips";
import { colors, spacing } from "@/constants/theme";

export const ATTACH_NOTICE = "서버에 저장하지 않고 비교 후 폐기해요";

export const ASK_PLACEHOLDER = "사진을 올리거나 물어보세요";

interface Props {
  value: string;
  photo: PhotoUpload | null;
  chips: Chip[];
  disabled: boolean;
  anchorTitle?: string | null;
  nearbyEnabled?: boolean;
  onClearAnchor?: () => void;
  onChange: (text: string) => void;
  onSuggest: (chip: Chip) => void;
  onNearby: () => void;
  onAttach: () => void;
  onShoot: () => void;
  onClearAttach: () => void;
  onSubmit: () => void;
}

export function AskComposer({
  value,
  photo,
  chips,
  disabled,
  anchorTitle = null,
  nearbyEnabled = false,
  onClearAnchor,
  onChange,
  onSuggest,
  onNearby,
  onAttach,
  onShoot,
  onClearAttach,
  onSubmit,
}: Props) {
  const ready = !disabled && (value.trim().length > 0 || photo !== null);

  return (
    <View style={styles.dock}>
      {anchorTitle ? (
        <View style={styles.anchorRow} testID="travel-anchor-banner">
          <View style={styles.anchorPill}>
            <Text style={styles.anchorTitle} numberOfLines={1}>
              {anchorTitle}
            </Text>
            <Pressable
              testID="travel-anchor-clear"
              accessibilityLabel="선택 해제"
              hitSlop={8}
              onPress={onClearAnchor}
            >
              <Icon name="close" size={13} color={colors.accentText} strokeWidth={2.4} />
            </Pressable>
          </View>
          <Text style={styles.anchorNote}>이 장소 기준으로 물어봐요</Text>
        </View>
      ) : null}
      {photo ? (
        <View style={styles.attach} testID="travel-attach-banner">
          <Image source={{ uri: photo.uri }} style={styles.attachThumb} contentFit="cover" />
          <View style={styles.attachCopy}>
            <Text style={styles.attachTitle}>사진 1장 첨부됨</Text>
            <Text style={styles.attachNote}>{ATTACH_NOTICE}</Text>
          </View>
          <Pressable testID="travel-attach-clear" hitSlop={8} onPress={onClearAttach}>
            <Icon name="close" size={16} color={colors.ter} strokeWidth={2} />
          </Pressable>
        </View>
      ) : null}

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
            style={({ pressed }) => [styles.chip, pressed && styles.chipPressed]}
            onPress={() => onSuggest(chip)}
          >
            <Text style={styles.chipText}>{chip.label}</Text>
          </Pressable>
        ))}
      </ScrollView>

      <View style={styles.composer}>
        <TextInput
          testID="travel-input"
          style={styles.input}
          value={value}
          onChangeText={onChange}
          placeholder={photo ? "사진에 덧붙일 말 (선택)" : ASK_PLACEHOLDER}
          placeholderTextColor={colors.ter}
          returnKeyType="send"
          onSubmitEditing={onSubmit}
          editable={!disabled}
        />
        <View style={styles.actions}>
          <View style={styles.actionsLeft}>
            <Pressable
              testID="travel-shoot"
              accessibilityLabel="사진 촬영"
              style={styles.attachButton}
              hitSlop={4}
              onPress={onShoot}
              disabled={disabled}
            >
              <Icon name="camera" size={17} color={colors.accent} strokeWidth={2} />
            </Pressable>
            <Pressable
              testID="travel-attach"
              accessibilityLabel="사진 올리기"
              style={styles.attachButton}
              hitSlop={4}
              onPress={onAttach}
              disabled={disabled}
            >
              <Icon name="image" size={17} color={colors.accent} strokeWidth={2} />
            </Pressable>
            {nearbyEnabled ? (
              <Pressable
                testID="travel-nearby"
                style={({ pressed }) => [styles.nearby, pressed && styles.chipPressed]}
                onPress={onNearby}
                disabled={disabled}
              >
                <Icon name="location" size={15} color={colors.sec} strokeWidth={1.9} />
                <Text style={styles.nearbyText}>{NEARBY_CHIP.label}</Text>
              </Pressable>
            ) : null}
          </View>
          <Pressable
            testID="travel-send"
            accessibilityLabel="보내기"
            style={[styles.send, ready && styles.sendReady]}
            onPress={onSubmit}
            disabled={!ready}
          >
            <Icon name="arrow-up" size={17} color={colors.onImage} strokeWidth={2.2} />
          </Pressable>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  dock: {
    backgroundColor: colors.bg,
    borderTopWidth: 1,
    borderTopColor: colors.line,
    paddingTop: 6,
  },
  anchorRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginHorizontal: spacing.lg,
    marginBottom: 2,
    marginTop: 2,
  },
  anchorPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 7,
    maxWidth: "60%",
    paddingVertical: 6,
    paddingLeft: 12,
    paddingRight: 8,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: "rgba(230,0,35,0.25)",
    backgroundColor: colors.accentFill,
  },
  anchorTitle: {
    flexShrink: 1,
    fontSize: 12,
    fontWeight: "800",
    letterSpacing: -0.2,
    color: colors.accentText,
  },
  anchorNote: { fontSize: 11, color: colors.ter },
  attach: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    marginHorizontal: spacing.lg,
    marginBottom: 6,
    paddingVertical: 8,
    paddingHorizontal: 10,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "rgba(230,0,35,0.24)",
    backgroundColor: colors.accentFill,
  },
  attachThumb: { width: 38, height: 38, borderRadius: 8 },
  attachCopy: { flex: 1 },
  attachTitle: { fontSize: 13, fontWeight: "700", letterSpacing: -0.2, color: colors.ink },
  attachNote: { marginTop: 2, fontSize: 11.5, color: colors.sec },
  chips: { gap: 8, paddingHorizontal: spacing.lg, paddingVertical: 6 },
  chip: {
    height: 34,
    paddingHorizontal: 16,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.bg,
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
  },
  chipPressed: { backgroundColor: colors.fill },
  chipText: { fontSize: 13.5, fontWeight: "700", color: colors.sec },
  composer: {
    marginTop: 4,
    marginHorizontal: spacing.lg,
    marginBottom: 14,
    paddingTop: 12,
    paddingHorizontal: 12,
    paddingBottom: 10,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.inset,
  },
  actions: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: 10,
  },
  actionsLeft: { flexDirection: "row", alignItems: "center", gap: 8 },
  attachButton: {
    width: 36,
    height: 36,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: "rgba(230,0,35,0.32)",
    alignItems: "center",
    justifyContent: "center",
  },
  nearby: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    height: 36,
    paddingHorizontal: 13,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: colors.line,
  },
  nearbyText: { fontSize: 13, fontWeight: "700", letterSpacing: -0.2, color: colors.sec },
  input: {
    minWidth: 0,
    minHeight: 22,
    padding: 0,
    paddingHorizontal: 2,
    fontSize: 14.5,
    fontWeight: "500",
    letterSpacing: -0.2,
    color: colors.ink,
  },
  send: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.control,
  },
  sendReady: { backgroundColor: colors.ink },
});
