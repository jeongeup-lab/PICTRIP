import { ScrollView, Pressable, View, Text, StyleSheet } from "react-native";
import { RemoteImage } from "@/components/RemoteImage";
import type { SpotCard } from "@/lib/api-types";
import { colors, spacing, radii } from "@/constants/theme";

interface Props {
  spots: SpotCard[];
  onPressItem: (contentId: string) => void;
}

export function SavedRail({ spots, onPressItem }: Props) {
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.rail}
    >
      {spots.map((s) => (
        <Pressable key={s.contentId} style={styles.item} onPress={() => onPressItem(s.contentId)}>
          <View style={styles.imgWrap}>
            <RemoteImage uri={s.firstImageUrl} style={styles.img} />
          </View>
          <Text numberOfLines={1} style={styles.name}>
            {s.title}
          </Text>
          {s.category ? (
            <Text numberOfLines={1} style={styles.cat}>
              {s.category}
            </Text>
          ) : null}
        </Pressable>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  rail: { gap: 12, paddingHorizontal: spacing.lg, paddingBottom: spacing.md },
  item: { width: 96 },
  imgWrap: {
    width: 96,
    height: 96,
    borderRadius: radii.md,
    overflow: "hidden",
    backgroundColor: colors.inset,
  },
  img: { width: "100%", height: "100%" },
  name: { fontSize: 12.5, fontWeight: "600", marginTop: 7, color: colors.ink },
  cat: { fontSize: 11.5, color: colors.ter, marginTop: 2 },
});
