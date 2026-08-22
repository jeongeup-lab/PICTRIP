import { Pressable, StyleSheet, Text, View } from "react-native";
import { RemoteImage } from "@/components/RemoteImage";
import { prefetchChannelCards, useChannels, useSeenChannels } from "@/features/channels/queries";
import type { ChannelCoords, ChannelKey, ChannelMeta } from "@/features/channels/api";
import { colors, radii, spacing } from "@/constants/theme";

const RING = 56;
const THUMB = RING - 4;

interface Props {
  coords: ChannelCoords | null;
  onOpen: (key: ChannelKey) => void;
}

export function ChannelStories({ coords, onOpen }: Props) {
  const { data } = useChannels(coords);
  const { seen } = useSeenChannels();
  const channels = data?.channels ?? [];
  if (channels.length === 0) return null;

  return (
    <View testID="channel-stories" style={styles.track}>
      {channels.map((meta) => (
        <ChannelStory
          key={meta.key}
          meta={meta}
          coords={coords}
          unseen={!seen.has(meta.key) && meta.available}
          onOpen={onOpen}
        />
      ))}
    </View>
  );
}

function ChannelStory({
  meta,
  coords,
  unseen,
  onOpen,
}: {
  meta: ChannelMeta;
  coords: ChannelCoords | null;
  unseen: boolean;
  onOpen: (key: ChannelKey) => void;
}) {
  return (
    <Pressable
      testID="channel-story"
      accessibilityRole="button"
      accessibilityLabel={`${meta.label} 채널 열기`}
      disabled={!meta.available}
      onPressIn={() => prefetchChannelCards(meta.key, coords)}
      onPress={() => onOpen(meta.key)}
      style={({ pressed }) => [
        styles.item,
        !meta.available && styles.dimmed,
        pressed && styles.pressed,
      ]}
    >
      <View style={[styles.ring, unseen && styles.ringUnseen]}>
        <RemoteImage uri={meta.thumbnailUrl} style={styles.thumb} radius={radii.pill} />
      </View>
      <Text style={styles.label} numberOfLines={1}>
        {meta.label}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  track: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingHorizontal: spacing.lg,
  },
  item: { width: RING, alignItems: "center", gap: 7 },
  ring: {
    width: RING,
    height: RING,
    borderRadius: radii.pill,
    padding: 2,
    backgroundColor: colors.line,
  },
  ringUnseen: { backgroundColor: colors.accent },
  thumb: {
    width: THUMB,
    height: THUMB,
    borderRadius: radii.pill,
    borderWidth: 2,
    borderColor: colors.bg,
  },
  label: {
    maxWidth: RING,
    fontSize: 9.5,
    fontWeight: "800",
    letterSpacing: 0,
    color: colors.ter,
  },
  dimmed: { opacity: 0.42 },
  pressed: { opacity: 0.7 },
});
