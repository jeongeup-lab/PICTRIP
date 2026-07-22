import { Pressable, View, Text, StyleSheet } from "react-native";
import { RemoteImage } from "@/components/RemoteImage";
import { Icon } from "@/components/Icon";
import type { ResolvedPlace } from "@/features/plan/api";
import { placeName } from "@/features/plan/lib/plan-format";
import { colors, radii } from "@/constants/theme";

interface Props {
  place: ResolvedPlace;
  selected: boolean;
  onPress: () => void;
}

export function PickRow({ place, selected, onPress }: Props) {
  const tip = place.extracted.tip ?? place.spot?.address ?? "";
  return (
    <Pressable
      testID={`pick-${placeName(place)}`}
      style={({ pressed }) => [styles.row, pressed && styles.pressed]}
      onPress={onPress}
    >
      <View style={[styles.box, selected && styles.boxOn]}>
        {selected ? <Icon name="check" size={12} color={colors.onImage} strokeWidth={2.4} /> : null}
      </View>
      <RemoteImage uri={place.spot?.imageUrl ?? null} style={styles.image} radius={radii.md} />
      <View style={styles.body}>
        <Text style={styles.title} numberOfLines={1}>
          {placeName(place)}
        </Text>
        {tip ? (
          <Text style={styles.tip} numberOfLines={1}>
            {tip}
          </Text>
        ) : null}
      </View>
    </Pressable>
  );
}

export function MissingRow({ place }: { place: ResolvedPlace }) {
  return (
    <View style={[styles.row, styles.missing]}>
      <View style={styles.box} />
      <View style={[styles.image, styles.imageVoid]}>
        <Text style={styles.voidMark}>?</Text>
      </View>
      <View style={styles.body}>
        <Text style={styles.title} numberOfLines={1}>
          {placeName(place)}
        </Text>
        <Text style={styles.tip} numberOfLines={1}>
          영상엔 나왔지만 장소 정보를 찾지 못했어요
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingVertical: 13,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  pressed: { backgroundColor: colors.fill },
  missing: { opacity: 0.38 },
  box: {
    width: 22,
    height: 22,
    borderRadius: radii.sm,
    borderWidth: 1.5,
    borderColor: colors.line,
    alignItems: "center",
    justifyContent: "center",
  },
  boxOn: { backgroundColor: colors.ink, borderColor: colors.ink },
  image: { width: 56, height: 56 },
  imageVoid: {
    backgroundColor: colors.inset,
    borderRadius: radii.md,
    alignItems: "center",
    justifyContent: "center",
  },
  voidMark: { fontSize: 13, fontWeight: "700", color: colors.ter },
  body: { flex: 1, gap: 3 },
  title: { fontSize: 15, fontWeight: "700", letterSpacing: -0.2, color: colors.ink },
  tip: { fontSize: 12.5, color: colors.sec },
});
