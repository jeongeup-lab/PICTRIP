import { Pressable, View, Text, StyleSheet } from "react-native";
import { RemoteImage } from "@/components/RemoteImage";
import { Icon } from "@/components/Icon";
import { subline } from "@/features/saved/lib/region";
import type { SpotCard } from "@/lib/api-types";
import { colors, radii } from "@/constants/theme";

interface Props {
  spot: SpotCard;
  onPress: () => void;
  onPressIn?: () => void;
  onUnsave: () => void;
  testID?: string;
}

export function SavedCard({ spot, onPress, onPressIn, onUnsave, testID }: Props) {
  const sub = subline(spot);

  return (
    <Pressable style={styles.card} onPress={onPress} onPressIn={onPressIn} testID={testID}>
      <View style={styles.frame}>
        <RemoteImage uri={spot.firstImageUrl} style={styles.img} />
        <Pressable
          style={styles.heart}
          onPress={onUnsave}
          hitSlop={8}
          accessibilityRole="button"
          accessibilityLabel="스크랩 해제"
          testID={testID ? `${testID}-unsave` : undefined}
        >
          <Icon name="bookmark-fill" size={17} color={colors.onImage} />
        </Pressable>
      </View>
      <Text numberOfLines={1} style={styles.name}>
        {spot.title}
      </Text>
      {sub ? (
        <Text numberOfLines={1} style={styles.sub}>
          {sub}
        </Text>
      ) : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: { width: "48.5%" },
  frame: {
    width: "100%",
    aspectRatio: 1,
    borderRadius: radii.md,
    overflow: "hidden",
    backgroundColor: colors.inset,
  },
  img: { width: "100%", height: "100%" },
  heart: {
    position: "absolute",
    top: 8,
    right: 8,
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: colors.control,
    alignItems: "center",
    justifyContent: "center",
  },
  name: {
    marginTop: 8,
    fontSize: 13.5,
    fontWeight: "600",
    color: colors.ink,
  },
  sub: {
    marginTop: 2,
    fontSize: 11.5,
    color: colors.ter,
  },
});
