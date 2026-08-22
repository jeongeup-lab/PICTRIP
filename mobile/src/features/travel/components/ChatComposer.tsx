import { useCallback, useState } from "react";
import { ActionSheetIOS, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { Image } from "expo-image";
import { Icon } from "@/components/Icon";
import { PHOTO_PICK_FAILED, PHOTO_SHOOT_FAILED } from "@/features/travel/lib/agent-errors";
import { pickTravelPhoto, shootTravelPhoto } from "@/features/travel/usecases/pick-travel-photo";
import type { FocusedSpot } from "@/features/travel/lib/anchor-actions";
import type { PhotoUpload } from "@/features/travel/api";
import { colors, radii, spacing } from "@/constants/theme";

export const ASK_PLACEHOLDER = "PICTRIP에게 물어보세요";
export const SUBJECT_SUFFIX = "에 대해 묻는 중";
export const SUBJECT_CLEAR_LABEL = "이 여행지에 대해 묻기 해제";
export const STREAMING_PLACEHOLDER = "답변을 만드는 중…";
export const ATTACH_HEADLINE = "이 사진 같은 분위기로 찾아요";
export const ATTACH_NOTICE = "사진은 저장하지 않아요";
export const ATTACH_SHOOT_LABEL = "촬영";
export const ATTACH_PICK_LABEL = "앨범에서 선택";
export const ATTACH_CANCEL_LABEL = "취소";
export const MAX_MESSAGE_CHARS = 500;

export function askPlaceholder(subject: FocusedSpot | null): string {
  return subject ? `${subject.title}에 대해 물어보세요` : ASK_PLACEHOLDER;
}

interface Props {
  streaming: boolean;
  subject: FocusedSpot | null;
  onSend: (text: string, photo: PhotoUpload | null) => void;
  onNotice: (message: string) => void;
  onClearSubject: () => void;
}

export function ChatComposer({ streaming, subject, onSend, onNotice, onClearSubject }: Props) {
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
            onPress={() => setPhoto(null)}
          >
            <Icon name="close" size={16} color={colors.ter} strokeWidth={2} />
          </Pressable>
        </View>
      ) : null}

      {subject && !photo ? (
        <View testID="travel-subject" style={styles.subject}>
          <View style={styles.subjectBadge}>
            <Text style={styles.subjectBadgeText}>{subject.index + 1}</Text>
          </View>
          <Text style={styles.subjectText} numberOfLines={1}>
            {subject.title}
            <Text style={styles.subjectSuffix}>{SUBJECT_SUFFIX}</Text>
          </Text>
          <Pressable
            testID="travel-subject-clear"
            accessibilityRole="button"
            accessibilityLabel={SUBJECT_CLEAR_LABEL}
            hitSlop={8}
            onPress={onClearSubject}
          >
            <Icon name="close" size={13} color={colors.ter} strokeWidth={2} />
          </Pressable>
        </View>
      ) : null}

      <View style={styles.field}>
        <TextInput
          testID="travel-input"
          style={styles.input}
          value={draft}
          onChangeText={setDraft}
          placeholder={streaming ? STREAMING_PLACEHOLDER : askPlaceholder(subject)}
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
  subject: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    alignSelf: "flex-start",
    maxWidth: "100%",
    height: 30,
    marginBottom: 9,
    paddingLeft: 7,
    paddingRight: 9,
    borderRadius: 15,
    borderWidth: 1,
    borderColor: colors.glassBorder,
    backgroundColor: colors.fill,
  },
  subjectBadge: {
    width: 18,
    height: 18,
    borderRadius: 9,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.accent,
  },
  subjectBadgeText: { fontSize: 10, fontWeight: "800", color: colors.onImage },
  subjectText: {
    flexShrink: 1,
    fontSize: 12,
    fontWeight: "600",
    letterSpacing: -0.2,
    color: colors.ink,
  },
  subjectSuffix: { fontWeight: "500", color: colors.ter },
  attachThumb: { width: 46, height: 46, borderRadius: 11 },
  attachCopy: { flex: 1 },
  attachTitle: { fontSize: 13.5, fontWeight: "700", letterSpacing: -0.2, color: colors.ink },
  attachNote: { marginTop: 3, fontSize: 11.5, color: colors.sec },
  field: {
    flexDirection: "row",
    alignItems: "flex-end",
    gap: 9,
    minHeight: 46,
    paddingLeft: 15,
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
