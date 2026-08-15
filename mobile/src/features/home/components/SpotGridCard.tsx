import { Pressable, StyleSheet, Text, View } from "react-native";
import Svg, { Defs, LinearGradient, Rect, Stop } from "react-native-svg";
import { RemoteImage } from "@/components/RemoteImage";
import { SaveButton } from "@/features/saved/components/SaveButton";
import type { HomeSpotCard } from "@/features/home/api";
import { colors } from "@/constants/theme";

interface Props {
  card: HomeSpotCard;
  width: number;
  subtitle: string;
  onPress: () => void;
}

const IMAGE_RATIO = 1.08;
const FOOTER_HEIGHT = 62;

export function SpotGridCard({ card, width, subtitle, onPress }: Props) {
  const imageHeight = Math.round(width * IMAGE_RATIO);
  return (
    <Pressable testID="home-grid-card" onPress={onPress} style={[styles.card, { width }]}>
      <View style={{ height: imageHeight }}>
        <RemoteImage uri={card.imageUrl} style={StyleSheet.absoluteFill} midSize />
        <Svg style={StyleSheet.absoluteFill} width="100%" height="100%" pointerEvents="none">
          <Defs>
            <LinearGradient id="homeCardScrim" x1="0" y1="0" x2="0" y2="1">
              <Stop offset="0" stopColor="#0B0D11" stopOpacity={0.72} />
              <Stop offset="0.5" stopColor="#0B0D11" stopOpacity={0.06} />
              <Stop offset="1" stopColor="#0B0D11" stopOpacity={0.18} />
            </LinearGradient>
          </Defs>
          <Rect x="0" y="0" width="100%" height="100%" fill="url(#homeCardScrim)" />
        </Svg>

        {card.rank === null ? null : (
          <>
            <Text testID="home-card-rank" style={styles.rank}>
              {card.rank}
            </Text>
            {card.tag ? (
              <Text style={styles.tag} numberOfLines={1}>
                #{card.tag}
              </Text>
            ) : null}
          </>
        )}
      </View>

      <View style={styles.footer}>
        <View style={styles.footerText}>
          <Text style={styles.title} numberOfLines={1}>
            {card.title}
          </Text>
          <Text style={styles.subtitle} numberOfLines={1}>
            {subtitle}
          </Text>
        </View>
        <SaveButton testID="home-save-button" contentId={card.contentId} />
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: { borderRadius: 16, overflow: "hidden", backgroundColor: colors.inset },
  rank: {
    position: "absolute",
    top: 4,
    left: 12,
    fontSize: 44,
    fontWeight: "900",
    fontStyle: "italic",
    letterSpacing: -2,
    color: colors.onImage,
  },
  tag: {
    position: "absolute",
    top: 56,
    left: 12,
    right: 12,
    fontSize: 14,
    fontWeight: "800",
    letterSpacing: -0.3,
    color: colors.onImage,
  },
  footer: {
    height: FOOTER_HEIGHT,
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingHorizontal: 12,
  },
  footerText: { flex: 1, gap: 3 },
  title: { fontSize: 14, fontWeight: "800", letterSpacing: -0.3, color: colors.ink },
  subtitle: { fontSize: 12.5, fontWeight: "600", color: colors.sec },
});
