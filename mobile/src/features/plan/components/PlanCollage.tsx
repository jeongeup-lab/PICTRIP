import { View, StyleSheet } from "react-native";
import { RemoteImage } from "@/components/RemoteImage";
import { colors, radii } from "@/constants/theme";

interface Props {
  images: string[];
}

export function PlanCollage({ images }: Props) {
  if (images.length === 0) return null;

  if (images.length === 1) {
    return (
      <View style={styles.frame}>
        <RemoteImage uri={images[0]} style={styles.full} midSize />
      </View>
    );
  }

  return (
    <View style={[styles.frame, styles.split]}>
      <RemoteImage uri={images[0]} style={styles.lead} midSize />
      <View style={styles.column}>
        <RemoteImage uri={images[1]} style={styles.stacked} midSize />
        <RemoteImage uri={images[2]} style={styles.stacked} midSize />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  frame: {
    height: 132,
    borderRadius: radii.lg,
    overflow: "hidden",
    backgroundColor: colors.inset,
  },
  split: { flexDirection: "row", gap: 4 },
  full: { flex: 1 },
  lead: { flex: 1.6 },
  column: { flex: 1, gap: 4 },
  stacked: { flex: 1 },
});
