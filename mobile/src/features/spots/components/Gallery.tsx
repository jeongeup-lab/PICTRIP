import { View, Text, Pressable, StyleSheet } from "react-native";
import { RemoteImage } from "@/components/RemoteImage";
import type { SpotImage } from "@/lib/api-types";
import { colors, radii } from "@/constants/theme";

interface GalleryProps {
  images: SpotImage[];
  firstImageUrl: string | null;
  onViewAll: () => void;
}

const MAX_THUMBS = 3;

export function Gallery({ images, firstImageUrl, onViewAll }: GalleryProps) {
  const uris =
    images.length > 0
      ? images.map((img) => img.smallImageUrl ?? img.originImageUrl)
      : firstImageUrl
        ? [firstImageUrl]
        : [];
  if (uris.length === 0) return null;
  const thumbs = uris.slice(0, MAX_THUMBS);
  const remaining = uris.length - thumbs.length;
  return (
    <Pressable style={styles.strip} onPress={onViewAll}>
      {thumbs.map((uri, i) => (
        <RemoteImage key={`${uri}-${i}`} uri={uri} radius={radii.md} style={styles.tile} />
      ))}
      {remaining > 0 ? (
        <View style={[styles.tile, styles.more]}>
          <Text style={styles.moreText}>+{remaining}</Text>
        </View>
      ) : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  strip: { flexDirection: "row", gap: 8, paddingHorizontal: 20, marginTop: 18 },
  tile: { width: 64, height: 64, borderRadius: radii.md },
  more: {
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.glassFill,
    borderWidth: 1,
    borderColor: colors.glassBorder,
  },
  moreText: { fontSize: 12, fontWeight: "700", color: colors.onImage },
});
