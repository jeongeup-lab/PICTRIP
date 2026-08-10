import { View, Text, Pressable, StyleSheet } from "react-native";
import { Image } from "expo-image";
import { Icon } from "@/components/Icon";
import type { Mood, MoodImage } from "@/features/travel/api";
import { colors, spacing } from "@/constants/theme";

export const GREETING_LINE1 = "사진 한 장이면 돼요.";
export const GREETING_LINE2 = "분위기가 닮은 국내 여행지를 찾아드릴게요.";
export const HERO_LABEL = "사진 올리기";
export const HERO_SUB = "앨범에서 고르거나 바로 촬영";

const COLLAGE_TILES: {
  mood: Mood;
  place: { top?: number; bottom?: number; left?: number; right?: number };
  tilt: string;
}[] = [
  { mood: "sea", place: { left: -16, top: 16 }, tilt: "-7deg" },
  { mood: "street", place: { right: -14, top: 6 }, tilt: "6deg" },
  { mood: "mountain", place: { left: 34, bottom: -14 }, tilt: "4deg" },
];

export function moodImageUri(images: MoodImage[] | undefined, mood: Mood): string | null {
  return images?.find((image) => image.code === mood)?.imageUrl ?? null;
}

interface Props {
  moodImages?: MoodImage[];
  onPickPhoto: () => void;
}

export function EmptyGreeting({ moodImages, onPickPhoto }: Props) {
  return (
    <View style={styles.root}>
      <Text style={styles.line1}>{GREETING_LINE1}</Text>
      <Text style={styles.line2}>{GREETING_LINE2}</Text>
      <Pressable
        testID="travel-photo-hero"
        accessibilityRole="button"
        accessibilityLabel={HERO_LABEL}
        style={({ pressed }) => [styles.hero, pressed && styles.pressed]}
        onPress={onPickPhoto}
      >
        <View style={styles.collage} pointerEvents="none">
          {COLLAGE_TILES.map((tile, index) => {
            const uri = moodImageUri(moodImages, tile.mood);
            if (!uri) return null;
            return (
              <Image
                key={tile.mood}
                testID={`travel-collage-${index}`}
                source={{ uri }}
                style={[styles.collageTile, tile.place, { transform: [{ rotate: tile.tilt }] }]}
                contentFit="cover"
                transition={180}
              />
            );
          })}
        </View>
        <View style={styles.veil} pointerEvents="none" />
        <View style={styles.badge}>
          <Icon name="camera" size={28} color={colors.onImage} strokeWidth={1.8} />
        </View>
        <Text style={styles.heroLabel}>{HERO_LABEL}</Text>
        <Text style={styles.heroSub}>{HERO_SUB}</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, gap: spacing.xs },
  line1: { fontSize: 19, fontWeight: "800", letterSpacing: -0.5, color: colors.ink },
  line2: { fontSize: 19, fontWeight: "800", letterSpacing: -0.5, color: colors.accentText },
  hero: {
    flex: 1,
    marginTop: spacing.sm,
    borderRadius: 20,
    overflow: "hidden",
    borderWidth: 1,
    borderColor: colors.accentFill,
    backgroundColor: colors.fill,
    alignItems: "center",
    justifyContent: "center",
    gap: 11,
  },
  collage: { position: "absolute", top: 0, right: 0, bottom: 0, left: 0, opacity: 0.34 },
  collageTile: { position: "absolute", width: 132, height: 96, borderRadius: 10 },
  veil: {
    position: "absolute",
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    backgroundColor: "rgba(0,0,0,0.42)",
  },
  badge: {
    width: 66,
    height: 66,
    borderRadius: 33,
    backgroundColor: colors.accent,
    alignItems: "center",
    justifyContent: "center",
  },
  heroLabel: { fontSize: 15.5, fontWeight: "800", letterSpacing: -0.3, color: colors.ink },
  heroSub: { fontSize: 12, letterSpacing: -0.2, color: colors.sec },
  pressed: { opacity: 0.75 },
});
