import { Pressable, View, Text, StyleSheet } from "react-native";
import { Icon } from "@/components/Icon";
import { colors, spacing } from "@/constants/theme";

export const PHOTO_CTA_TITLE = "사진으로 찾기";
export const PHOTO_CTA_BODY = "가고 싶은 분위기의 사진 한 장이면 돼요";
export const LOCATION_PRIMER_TEXT = "위치를 켜면 내 근처로 물어볼 수 있어요";
export const LOCATION_PRIMER_ACTION = "켜기";

interface Props {
  onPickPhoto: () => void;
  onAskLocation?: () => void;
  locationAskable?: boolean;
}

export function StartActions({ onPickPhoto, onAskLocation, locationAskable = false }: Props) {
  return (
    <View style={styles.root}>
      <Pressable
        testID="travel-start-photo"
        accessibilityRole="button"
        style={({ pressed }) => [styles.photo, pressed && styles.photoPressed]}
        onPress={onPickPhoto}
      >
        <View style={styles.icon}>
          <Icon name="image" size={20} color={colors.accent} strokeWidth={1.9} />
        </View>
        <View style={styles.copy}>
          <Text style={styles.title}>{PHOTO_CTA_TITLE}</Text>
          <Text style={styles.body}>{PHOTO_CTA_BODY}</Text>
        </View>
      </Pressable>

      {locationAskable ? (
        <Pressable
          testID="travel-start-location"
          accessibilityRole="button"
          style={({ pressed }) => [styles.primer, pressed && styles.primerPressed]}
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
  root: { width: "100%", maxWidth: 320, marginTop: 26, gap: 10 },
  photo: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingVertical: 15,
    paddingHorizontal: 16,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "rgba(230,0,35,0.3)",
    backgroundColor: colors.accentFill,
  },
  photoPressed: { opacity: 0.85 },
  icon: {
    width: 40,
    height: 40,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "rgba(230,0,35,0.24)",
    backgroundColor: colors.bg,
    alignItems: "center",
    justifyContent: "center",
  },
  copy: { flex: 1 },
  title: { fontSize: 14.5, fontWeight: "800", letterSpacing: -0.3, color: colors.accentText },
  body: { marginTop: 2, fontSize: 11.5, lineHeight: 16, color: colors.sec },
  primer: {
    flexDirection: "row",
    alignItems: "center",
    gap: 9,
    paddingVertical: 11,
    paddingHorizontal: spacing.md,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.inset,
  },
  primerPressed: { backgroundColor: colors.fill },
  primerText: {
    flex: 1,
    fontSize: 12.5,
    fontWeight: "700",
    letterSpacing: -0.2,
    color: colors.sec,
  },
  primerAction: { fontSize: 11.5, fontWeight: "800", color: colors.accentText },
});
