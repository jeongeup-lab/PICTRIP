import { useCallback, useState } from "react";
import { ActionSheetIOS, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { Image } from "expo-image";
import { Icon } from "@/components/Icon";
import { PHOTO_PICK_FAILED, PHOTO_SHOOT_FAILED } from "@/features/travel/lib/agent-errors";
import { pickTravelPhoto, shootTravelPhoto } from "@/features/travel/usecases/pick-travel-photo";
import type { PhotoUpload } from "@/features/travel/api";
import { colors, radii, spacing } from "@/constants/theme";

export const ASK_PLACEHOLDER = "PICTRIP에게 물어보세요";
export const PHOTO_PLACEHOLDER = "사진과 함께 물어보세요";
export const STREAMING_PLACEHOLDER = "답변을 만드는 중…";
export const ATTACH_NOTICE = "사진은 저장하지 않아요 · 지역을 함께 쓰면 그 안에서 찾아요";
export const ATTACH_SHOOT_LABEL = "촬영";
export const ATTACH_PICK_LABEL = "앨범에서 선택";
export const ATTACH_CANCEL_LABEL = "취소";
export const MAX_MESSAGE_CHARS = 500;

interface Props {
  streaming: boolean;
  onSend: (text: string, photo: PhotoUpload | null) => void;
  onNotice: (message: string) => void;
}

export function ChatComposer({ streaming, onSend, onNotice }: Props) {
  const [draft, setDraft] = useState("");
  const [photo, setPhoto] = useState<PhotoUpload | null>(null);

  const ready = !streaming && (draft.trim().length > 0 || photo !== null);

  const submit = useCallback(() => {
    if (streaming) return;
    if (draft.trim().length === 0 && photo === null) return;
    onSend(draft, photo);
    setDraft("");
    setPhoto(null);
  }, [streaming, draft, photo, onSend]);

  const attachFromAlbum = useCallback(async () => {
    try {
      const picked = await pickTravelPhoto();
      if (picked) setPhoto(picked);
    } catch {
      onNotice(PHOTO_PICK_FAILED);
    }
  }, [onNotice]);

  const attachFromCamera = useCallback(async () => {
    try {
      const picked = await shootTravelPhoto();
      if (picked) setPhoto(picked);
    } catch {
      onNotice(PHOTO_SHOOT_FAILED);
    }
  }, [onNotice]);

  const onAttach = useCallback(() => {
    ActionSheetIOS.showActionSheetWithOptions(
      {
        options: [ATTACH_SHOOT_LABEL, ATTACH_PICK_LABEL, ATTACH_CANCEL_LABEL],
        cancelButtonIndex: 2,
      },
      (choice) => {
        if (choice === 0) void attachFromCamera();
        if (choice === 1) void attachFromAlbum();
      },
    );
  }, [attachFromCamera, attachFromAlbum]);

  return (
    <View style={styles.root} pointerEvents="box-none">
      {photo ? (
        <Text testID="travel-attach-banner" style={styles.notice}>
          {ATTACH_NOTICE}
        </Text>
      ) : null}

      <View style={styles.field}>
        {photo ? (
          <View style={styles.attached}>
            <Image source={{ uri: photo.uri }} style={styles.attachedThumb} contentFit="cover" />
            <Pressable
              testID="travel-attach-clear"
              accessibilityRole="button"
              accessibilityLabel="첨부 사진 제거"
              hitSlop={10}
              style={styles.attachedClear}
              onPress={() => setPhoto(null)}
            >
              <Icon name="close" size={9} color={colors.bg} strokeWidth={3.2} />
            </Pressable>
          </View>
        ) : null}
        <TextInput
          testID="travel-input"
          style={styles.input}
          value={draft}
          onChangeText={setDraft}
          placeholder={
            streaming ? STREAMING_PLACEHOLDER : photo ? PHOTO_PLACEHOLDER : ASK_PLACEHOLDER
          }
          placeholderTextColor={colors.ter}
          returnKeyType="send"
          submitBehavior="blurAndSubmit"
          onSubmitEditing={submit}
          editable={!streaming}
          maxLength={MAX_MESSAGE_CHARS}
          multiline
        />
        <Pressable
          testID="travel-attach"
          accessibilityRole="button"
          accessibilityLabel="사진 첨부"
          style={styles.iconButton}
          hitSlop={4}
          onPress={onAttach}
          disabled={streaming}
        >
          <Icon name="camera" size={17} color={colors.sec} strokeWidth={1.9} />
        </Pressable>
        <Pressable
          testID="travel-send"
          accessibilityRole="button"
          accessibilityLabel="보내기"
          style={[styles.send, ready && styles.sendReady]}
          onPress={submit}
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

const styles = StyleSheet.create({
  root: { paddingHorizontal: spacing.md, paddingBottom: 12 },
  notice: {
    marginBottom: 8,
    marginLeft: 4,
    fontSize: 11.5,
    lineHeight: 16,
    letterSpacing: -0.1,
    color: colors.ter,
  },
  attached: { width: 30, height: 30, marginBottom: 2 },
  attachedThumb: { width: 30, height: 30, borderRadius: 8 },
  attachedClear: {
    position: "absolute",
    top: -5,
    right: -5,
    width: 15,
    height: 15,
    borderRadius: 8,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.ink,
  },
  field: {
    flexDirection: "row",
    alignItems: "flex-end",
    gap: 9,
    minHeight: 46,
    paddingLeft: 13,
    paddingRight: 6,
    paddingVertical: 6,
    borderRadius: 23,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.raiseStrong,
  },
  input: {
    flex: 1,
    minWidth: 0,
    maxHeight: 96,
    padding: 0,
    paddingVertical: 7,
    fontSize: 15,
    fontWeight: "600",
    letterSpacing: -0.2,
    color: colors.ink,
  },
  iconButton: { width: 30, height: 32, alignItems: "center", justifyContent: "center" },
  send: {
    width: 32,
    height: 32,
    borderRadius: radii.pill,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.fillStrong,
  },
  sendReady: { backgroundColor: colors.accent },
});
