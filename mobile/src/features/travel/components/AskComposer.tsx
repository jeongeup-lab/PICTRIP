import { ScrollView, Pressable, View, Text, TextInput, StyleSheet } from "react-native";
import { Image } from "expo-image";
import { Icon } from "@/components/Icon";
import type { PhotoUpload } from "@/features/travel/api";
import { colors, spacing } from "@/constants/theme";

export const ATTACH_NOTICE = "서버에 저장하지 않고 비교 후 폐기해요";

interface Props {
  value: string;
  photo: PhotoUpload | null;
  suggestions: string[];
  disabled: boolean;
  onChange: (text: string) => void;
  onSuggest: (text: string) => void;
  onAttach: () => void;
  onClearAttach: () => void;
  onSubmit: () => void;
}

export function AskComposer({
  value,
  photo,
  suggestions,
  disabled,
  onChange,
  onSuggest,
  onAttach,
  onClearAttach,
  onSubmit,
}: Props) {
  const ready = !disabled && (value.trim().length > 0 || photo !== null);

  return (
    <View style={styles.dock}>
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
        {suggestions.map((text) => (
          <Pressable
            key={text}
            testID={`travel-chip-${text}`}
            style={({ pressed }) => [styles.chip, pressed && styles.chipPressed]}
            onPress={() => onSuggest(text)}
          >
            <Text style={styles.chipText}>{text}</Text>
          </Pressable>
        ))}
      </ScrollView>

      <View style={styles.composer}>
        <Pressable
          testID="travel-attach"
          style={styles.iconButton}
          hitSlop={4}
          onPress={onAttach}
          disabled={disabled}
        >
          <Icon name="plus" size={20} color={colors.sec} strokeWidth={2} />
        </Pressable>
        <TextInput
          testID="travel-input"
          style={styles.input}
          value={value}
          onChangeText={onChange}
          placeholder={photo ? "사진에 덧붙일 말 (선택)" : "무엇이든 물어보세요"}
          placeholderTextColor={colors.ter}
          returnKeyType="send"
          onSubmitEditing={onSubmit}
          editable={!disabled}
        />
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
  );
}

const styles = StyleSheet.create({
  dock: {
    backgroundColor: colors.bg,
    borderTopWidth: 1,
    borderTopColor: colors.line,
    paddingTop: 6,
  },
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
    borderColor: "rgba(3,199,90,0.28)",
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
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginTop: 4,
    marginHorizontal: spacing.lg,
    marginBottom: 14,
    padding: 5,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.inset,
  },
  iconButton: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
  },
  input: {
    flex: 1,
    minWidth: 0,
    fontSize: 14.5,
    fontWeight: "500",
    letterSpacing: -0.2,
    color: colors.ink,
    padding: 0,
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
