import { ScrollView, View, Text, Pressable, StyleSheet } from "react-native";
import { RemoteImage } from "@/components/RemoteImage";
import { Icon } from "@/components/Icon";
import type { SpotImage } from "@/lib/api-types";
import { colors } from "@/constants/theme";

interface GalleryProps {
  images: SpotImage[];
  firstImageUrl: string | null;
  onViewAll: () => void;
}

/** Hero gallery strip (first tile wide, rest narrow) + 전체 사진 glass button. */
export function Gallery({ images, firstImageUrl, onViewAll }: GalleryProps) {
  const uris =
    images.length > 0
      ? images.map((img) => img.smallImageUrl ?? img.originImageUrl)
      : firstImageUrl
        ? [firstImageUrl]
        : [];
  if (uris.length === 0) return null;
  return (
    <View>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.strip}
      >
        {uris.map((uri, i) => (
          <RemoteImage
            key={`${uri}-${i}`}
            uri={uri}
            radius={6}
            style={[styles.tile, i === 0 ? styles.wide : styles.narrow]}
          />
        ))}
      </ScrollView>
      <Pressable style={styles.allBtn} onPress={onViewAll}>
        <Icon name="image" size={20} color={colors.onImage} />
        <Text style={styles.allText}>전체 사진</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  strip: { gap: 7, paddingHorizontal: 20, marginTop: 22 },
  tile: { height: 236 },
  wide: { width: 300 },
  narrow: { width: 108 },
  allBtn: {
    height: 56,
    marginHorizontal: 20,
    marginTop: 14,
    borderRadius: 12,
    backgroundColor: colors.glassFill,
    borderWidth: 1,
    borderColor: colors.glassBorder,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 9,
  },
  allText: { color: colors.onImage, fontSize: 16, fontWeight: "700" },
});
