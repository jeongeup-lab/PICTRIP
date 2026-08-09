import { View, Text, Pressable, StyleSheet } from "react-native";
import { TravelerAvatar } from "@/features/travel/components/TravelerAvatar";
import { colors, spacing } from "@/constants/theme";

export const GREETING_LINE1 = "어떤 분위기의 여행을 꿈꾸세요?";
export const GREETING_LINE2 =
  "사진 한 장 보여주시면, 그 분위기를 닮은 우리나라 여행지를 찾아드릴게요.";
export const ACCENT_SPAN = "그 분위기를 닮은 우리나라 여행지";
export const SAMPLES_CAPTION = "지금 사진이 없다면, 이런 분위기는 어때요?";
export const SAMPLE_MOODS: { label: string; question: string }[] = [
  { label: "바다 노을", question: "바다 노을이 예쁜 여행지 알려줘" },
  { label: "감성 골목", question: "감성적인 골목길 여행지 알려줘" },
  { label: "숲길", question: "걷기 좋은 숲길 여행지 알려줘" },
];

export const ALBUM_CTA = "앨범에서 사진 고르기";
export const SHOOT_CTA = "카메라 촬영";

const TILE_TONES = ["#C74B50", "#3B4664", "#1E5E58"] as const;

const accentAt = GREETING_LINE2.indexOf(ACCENT_SPAN);
const LINE2_PREFIX = GREETING_LINE2.slice(0, accentAt);
const LINE2_SUFFIX = GREETING_LINE2.slice(accentAt + ACCENT_SPAN.length);

interface Props {
  onSample: (question: string) => void;
  onAlbum: () => void;
  onShoot: () => void;
}

export function EmptyGreeting({ onSample, onAlbum, onShoot }: Props) {
  return (
    <View style={styles.root}>
      <View style={styles.greeting}>
        <TravelerAvatar />
        <View style={styles.bubble}>
          <Text style={styles.line1}>{GREETING_LINE1}</Text>
          <Text style={styles.line2}>
            {LINE2_PREFIX}
            <Text style={styles.line2Accent}>{ACCENT_SPAN}</Text>
            {LINE2_SUFFIX}
          </Text>
        </View>
      </View>
      <Text style={styles.caption}>{SAMPLES_CAPTION}</Text>
      <View style={styles.tiles}>
        {SAMPLE_MOODS.map((mood, index) => (
          <Pressable
            key={mood.label}
            testID={`travel-sample-${index}`}
            accessibilityRole="button"
            accessibilityLabel={mood.label}
            style={({ pressed }) => [
              styles.tile,
              { backgroundColor: TILE_TONES[index % TILE_TONES.length] },
              pressed && styles.pressed,
            ]}
            onPress={() => onSample(mood.question)}
          >
            <Text style={styles.tileLabel}>{mood.label}</Text>
          </Pressable>
        ))}
      </View>
      <View style={styles.ctas}>
        <Pressable
          testID="travel-empty-album"
          accessibilityRole="button"
          accessibilityLabel={ALBUM_CTA}
          style={({ pressed }) => [styles.cta, styles.ctaPrimary, pressed && styles.pressed]}
          onPress={onAlbum}
        >
          <Text style={styles.ctaPrimaryText}>{ALBUM_CTA}</Text>
        </Pressable>
        <Pressable
          testID="travel-empty-shoot"
          accessibilityRole="button"
          accessibilityLabel={SHOOT_CTA}
          style={({ pressed }) => [styles.cta, styles.ctaGhost, pressed && styles.pressed]}
          onPress={onShoot}
        >
          <Text style={styles.ctaGhostText}>{SHOOT_CTA}</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { gap: spacing.md },
  greeting: { flexDirection: "row", alignItems: "flex-start", gap: spacing.sm },
  bubble: {
    flex: 1,
    backgroundColor: colors.fill,
    borderWidth: 1,
    borderColor: colors.line,
    borderTopLeftRadius: 4,
    borderTopRightRadius: 16,
    borderBottomLeftRadius: 16,
    borderBottomRightRadius: 16,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    gap: 6,
  },
  line1: { fontSize: 16, fontWeight: "700", letterSpacing: -0.3, color: colors.ink },
  line2: { fontSize: 13, lineHeight: 19, letterSpacing: -0.2, color: colors.sec },
  line2Accent: { color: colors.accentText },
  caption: { fontSize: 12, letterSpacing: -0.2, color: colors.ter },
  tiles: { flexDirection: "row", gap: spacing.xs },
  tile: {
    flex: 1,
    height: 76,
    borderRadius: 12,
    justifyContent: "flex-end",
    padding: spacing.sm,
  },
  tileLabel: { fontSize: 11, fontWeight: "800", letterSpacing: -0.2, color: colors.onImage },
  ctas: { gap: spacing.xs },
  cta: {
    height: 46,
    borderRadius: 13,
    alignItems: "center",
    justifyContent: "center",
  },
  ctaPrimary: { backgroundColor: colors.accent },
  ctaPrimaryText: { fontSize: 14, fontWeight: "700", letterSpacing: -0.2, color: colors.onImage },
  ctaGhost: { backgroundColor: colors.fill, borderWidth: 1, borderColor: colors.line },
  ctaGhostText: { fontSize: 14, fontWeight: "600", letterSpacing: -0.2, color: colors.ink },
  pressed: { opacity: 0.7 },
});
