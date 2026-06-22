import { View, Text, StyleSheet } from "react-native";
import Svg, { Circle } from "react-native-svg";
import { bucketFor } from "@/features/photo/lib/similarity-bucket";
import { colors } from "@/constants/theme";

interface Props {
  similarity: number;
  size?: number;
}

/** Circular ring filled to the bucket tier (no raw %), plus the bucket label.
 * Rendered on the dark glass result bar — stroke/text are on-image white. */
export function SimilarityGauge({ similarity, size = 44 }: Props) {
  const { label, tier } = bucketFor(similarity);
  const stroke = 3;
  const r = size / 2 - stroke;
  const circumference = 2 * Math.PI * r;
  return (
    <View style={styles.wrap}>
      <Svg width={size} height={size}>
        <Circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke={colors.glassBorder}
          strokeWidth={stroke}
          fill="none"
        />
        <Circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke={colors.onImage}
          strokeWidth={stroke}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - tier)}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </Svg>
      <Text style={styles.label}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { alignItems: "center", gap: 3, flexShrink: 0 },
  label: { fontSize: 11, fontWeight: "700", color: colors.onImage },
});
