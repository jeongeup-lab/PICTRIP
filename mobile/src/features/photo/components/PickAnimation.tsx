import { Animated, StyleSheet, View } from "react-native";
import { StickFigure } from "@/features/photo/components/StickFigure";
import { usePickAnimation } from "@/features/photo/hooks/use-pick-animation";
import type { PickedImage } from "@/features/photo/usecases/pick-image";
import { colors, radii } from "@/constants/theme";

type Status = "idle" | "loading" | "success" | "error";

interface PickAnimationProps {
  asset: PickedImage | null;
  status: Status;
  onFinaleComplete: () => void;
}

const STAGE_W = 224;
const STAGE_H = 172;
const CARD_W = 46;
const CARD_H = 60;
const FIGURE_SIZE = 96;

/**
 * The brand mark come alive: the PicTrip stick figure hopping between
 * scattered candidate photo cards while the CLIP search runs, then landing
 * on — and revealing — the picked card once the search succeeds.
 */
export function PickAnimation({ asset, status, onFinaleComplete }: PickAnimationProps) {
  const { cards, figureX, figureY, figureArc, standOpacity, leapOpacity, heroOpacity } =
    usePickAnimation(status, onFinaleComplete);

  return (
    <View style={styles.stage} pointerEvents="none">
      {cards.map((card, i) => {
        const cardStyle = [
          styles.card,
          card.hero && styles.hero,
          {
            left: STAGE_W / 2 + card.x - CARD_W / 2,
            top: STAGE_H / 2 + card.y - CARD_H / 2,
            transform: [{ rotate: `${card.rotate}deg` }],
          },
        ];
        if (!card.hero) return <View key={i} style={cardStyle} />;
        return (
          <View key={i} style={cardStyle}>
            {asset ? (
              <Animated.Image
                source={{ uri: asset.uri }}
                style={[styles.heroImage, { opacity: heroOpacity }]}
              />
            ) : null}
          </View>
        );
      })}

      <Animated.View
        style={[
          styles.figureAnchor,
          {
            left: STAGE_W / 2 - FIGURE_SIZE / 2,
            top: STAGE_H / 2 - FIGURE_SIZE / 2,
            transform: [
              { translateX: figureX },
              { translateY: figureY },
              { translateY: figureArc },
            ],
          },
        ]}
      >
        <StickFigure size={FIGURE_SIZE} standOpacity={standOpacity} leapOpacity={leapOpacity} />
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  stage: { width: STAGE_W, height: STAGE_H, marginBottom: 16 },
  card: {
    position: "absolute",
    width: CARD_W,
    height: CARD_H,
    borderRadius: radii.md,
    backgroundColor: colors.skeleton,
    borderWidth: 1,
    borderColor: colors.line,
  },
  hero: {
    backgroundColor: colors.bg,
    borderColor: colors.control,
    borderStyle: "dashed",
    overflow: "hidden",
  },
  heroImage: { width: "100%", height: "100%" },
  figureAnchor: { position: "absolute", width: FIGURE_SIZE, height: FIGURE_SIZE },
});
