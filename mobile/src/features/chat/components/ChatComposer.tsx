import { useState } from "react";
import { View, TextInput, Pressable, StyleSheet } from "react-native";
import { Icon } from "@/components/Icon";
import { colors, spacing } from "@/constants/theme";

interface Props {
  disabled: boolean;
  placeholder: string;
  onSend: (text: string) => void;
}

export function ChatComposer({ disabled, placeholder, onSend }: Props) {
  const [text, setText] = useState("");
  const submit = () => {
    const t = text.trim();
    if (!t || disabled) return;
    setText("");
    onSend(t);
  };
  const inactive = disabled || !text.trim();
  return (
    <View style={styles.row}>
      <TextInput
        style={styles.field}
        value={text}
        onChangeText={setText}
        placeholder={placeholder}
        placeholderTextColor={colors.ter}
        returnKeyType="send"
        onSubmitEditing={submit}
        editable={!disabled}
      />
      <Pressable style={[styles.send, inactive && styles.sendDim]} onPress={submit}>
        <Icon name="chevron-right" size={20} color={colors.onImage} />
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
  },
  field: {
    flex: 1,
    height: 46,
    borderRadius: 23,
    backgroundColor: colors.inset,
    paddingHorizontal: 16,
    fontSize: 14,
    color: colors.ink,
  },
  send: {
    width: 46,
    height: 46,
    borderRadius: 23,
    backgroundColor: colors.ink,
    alignItems: "center",
    justifyContent: "center",
  },
  sendDim: { opacity: 0.35 },
});
