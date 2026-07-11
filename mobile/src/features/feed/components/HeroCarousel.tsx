import { useState } from "react";
import {
  View,
  Text,
  Pressable,
  ScrollView,
  useWindowDimensions,
  StyleSheet,
  type NativeSyntheticEvent,
  type NativeScrollEvent,
} from "react-native";
import { router } from "expo-router";
import { RemoteImage } from "@/components/RemoteImage";
import type { HeroTile } from "@/lib/api-types";
import { colors, radii } from "@/constants/theme";

export function HeroCarousel({ heroes }: { heroes: HeroTile[] }) {
  const { width } = useWindowDimensions();
  const cardWidth = width - 32;
  const [index, setIndex] = useState(0);

  const onScroll = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    const next = Math.round(e.nativeEvent.contentOffset.x / (cardWidth + 12));
    setIndex(Math.min(Math.max(next, 0), heroes.length - 1));
  };

  return (
    <ScrollView
      horizontal
      snapToInterval={cardWidth + 12}
      decelerationRate="fast"
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={{ paddingHorizontal: 16, gap: 12 }}
      onMomentumScrollEnd={onScroll}
    >
      {heroes.map((hero) => (
        <Pressable
          key={hero.id}
          style={{ width: cardWidth }}
          onPress={() => router.push(`/curations/${hero.slug}`)}
        >
          <RemoteImage
            uri={hero.coverUrl}
            radius={radii.lg}
            style={{ width: cardWidth, height: 280 }}
          />
          <View style={styles.scrim} pointerEvents="none" />
          <View style={styles.chip} pointerEvents="none">
            <Text style={styles.chipText}>큐레이션</Text>
          </View>
          <View style={styles.copy} pointerEvents="none">
            <Text style={styles.title}>{hero.title}</Text>
            {hero.subtitle ? <Text style={styles.subtitle}>{hero.subtitle}</Text> : null}
          </View>
          <View style={styles.counter} pointerEvents="none">
            <Text testID="hero-counter" style={styles.counterText}>
              {`${index + 1} / ${heroes.length}`}
            </Text>
          </View>
        </Pressable>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scrim: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    height: "58%",
    borderBottomLeftRadius: radii.lg,
    borderBottomRightRadius: radii.lg,
    backgroundColor: colors.scrimStrong,
  },
  chip: {
    position: "absolute",
    left: 16,
    top: 14,
    backgroundColor: "rgba(20,18,22,0.45)",
    borderRadius: 5,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  chipText: {
    fontSize: 10.5,
    fontWeight: "700",
    letterSpacing: 0.5,
    color: "rgba(255,255,255,0.92)",
  },
  copy: { position: "absolute", left: 16, right: 16, bottom: 16 },
  title: {
    fontSize: 21,
    fontWeight: "800",
    letterSpacing: -0.45,
    color: colors.onImage,
    lineHeight: 27,
  },
  subtitle: { marginTop: 4, fontSize: 13, color: colors.onDim },
  counter: {
    position: "absolute",
    right: 12,
    bottom: 14,
    backgroundColor: "rgba(20,18,22,0.5)",
    borderRadius: 11,
    paddingHorizontal: 10,
    paddingVertical: 3,
  },
  counterText: { fontSize: 11, fontWeight: "600", color: "rgba(255,255,255,0.9)" },
});
