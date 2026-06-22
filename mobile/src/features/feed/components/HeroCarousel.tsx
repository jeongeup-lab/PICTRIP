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
  const cardWidth = width - 40;
  const [index, setIndex] = useState(0);

  const onScroll = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    setIndex(Math.round(e.nativeEvent.contentOffset.x / (cardWidth + 12)));
  };

  return (
    <View>
      <ScrollView
        horizontal
        snapToInterval={cardWidth + 12}
        decelerationRate="fast"
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={{ paddingHorizontal: 20, gap: 12 }}
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
              radius={radii.xl}
              style={{ width: cardWidth, height: cardWidth * 1.1 }}
            />
            <View style={styles.scrim} pointerEvents="none" />
            <View style={styles.copy} pointerEvents="none">
              <Text style={styles.title}>{hero.title}</Text>
              {hero.subtitle ? <Text style={styles.subtitle}>{hero.subtitle}</Text> : null}
            </View>
          </Pressable>
        ))}
      </ScrollView>

      <View style={styles.dots}>
        {heroes.map((hero, i) => (
          <View
            key={hero.id}
            style={[styles.dot, { backgroundColor: i === index ? colors.ink : colors.line }]}
          />
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  scrim: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    height: "55%",
    borderBottomLeftRadius: radii.xl,
    borderBottomRightRadius: radii.xl,
    backgroundColor: colors.scrimStrong,
  },
  copy: { position: "absolute", left: 20, right: 20, bottom: 22 },
  title: {
    fontSize: 30,
    fontWeight: "800",
    letterSpacing: -0.6,
    color: colors.onImage,
    lineHeight: 36,
  },
  subtitle: { marginTop: 6, fontSize: 15, color: colors.onDim },
  dots: { flexDirection: "row", justifyContent: "center", gap: 7, paddingVertical: 14 },
  dot: { width: 7, height: 7, borderRadius: 4 },
});
