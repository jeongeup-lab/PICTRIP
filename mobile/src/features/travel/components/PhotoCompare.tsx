import { View, Text, StyleSheet } from "react-native";
import { Image } from "expo-image";
import { RemoteImage } from "@/components/RemoteImage";
import type { PhotoUpload, TravelSpot } from "@/features/travel/api";
import { colors } from "@/constants/theme";

export const MINE_LABEL = "올린 사진";
export const DISCARD_NOTE = "원본은 비교 후 바로 폐기했어요";

interface Props {
  photo: PhotoUpload;
  match: TravelSpot;
}

export function PhotoCompare({ photo, match }: Props) {
  return (
    <View style={styles.root} testID="travel-photo-compare">
      <View style={styles.row}>
        <View style={styles.half}>
          <Image source={{ uri: photo.uri }} style={styles.shot} contentFit="cover" />
          <Text style={styles.caption} numberOfLines={1}>
            {MINE_LABEL}
          </Text>
        </View>

        <View style={styles.link}>
          <Text style={styles.linkText}>≈</Text>
        </View>

        <View style={styles.half}>
          <RemoteImage uri={match.imageUrl} style={styles.shot} />
          <Text style={styles.caption} numberOfLines={1}>
            {match.tag ? `${match.title} · ${match.tag}` : match.title}
          </Text>
        </View>
      </View>

      <Text style={styles.note}>{DISCARD_NOTE}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { marginTop: 14, paddingTop: 14, borderTopWidth: 1, borderTopColor: colors.line },
  row: { flexDirection: "row", alignItems: "center", gap: 10 },
  half: { flex: 1, minWidth: 0 },
  shot: { width: "100%", height: 84, borderRadius: 10, backgroundColor: colors.skeleton },
  caption: {
    marginTop: 6,
    fontSize: 10.5,
    fontWeight: "800",
    letterSpacing: -0.1,
    color: colors.ter,
  },
  link: {
    width: 26,
    height: 26,
    borderRadius: 13,
    borderWidth: 1,
    borderColor: "rgba(230,0,35,0.22)",
    backgroundColor: colors.accentFill,
    alignItems: "center",
    justifyContent: "center",
  },
  linkText: { fontSize: 12, fontWeight: "800", color: colors.accentText },
  note: { marginTop: 10, fontSize: 11.5, color: colors.ter },
});
