import { ScrollView, Pressable, View, Text, StyleSheet } from "react-native";
import Svg, { Defs, LinearGradient, Stop, Rect } from "react-native-svg";
import { RemoteImage } from "@/components/RemoteImage";
import { prefetchChannelCards, useChannels, useSeenChannels } from "@/features/channels/queries";
import type { ChannelKey, ChannelMeta } from "@/features/channels/api";
import { colors } from "@/constants/theme";

interface Props {
  onOpen: (key: ChannelKey) => void;
}

export function ChannelTiles({ onOpen }: Props) {
  const { data } = useChannels();
  const { seen } = useSeenChannels();
  const channels = data?.channels ?? [];
  if (channels.length === 0) return null;
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.row}
    >
      {channels.map((meta) => (
        <ChannelTile key={meta.key} meta={meta} seen={seen.has(meta.key)} onOpen={onOpen} />
      ))}
    </ScrollView>
  );
}

function ChannelTile({
  meta,
  seen,
  onOpen,
}: {
  meta: ChannelMeta;
  seen: boolean;
  onOpen: (key: ChannelKey) => void;
}) {
  const dimmed = seen || !meta.available;
  const showBadge = !seen && meta.available;
  return (
    <Pressable
      testID="channel-tile"
      onPressIn={() => prefetchChannelCards(meta.key)}
      onPress={() => onOpen(meta.key)}
      disabled={!meta.available}
      style={[styles.tile, dimmed && styles.dimmed]}
    >
      <RemoteImage uri={meta.thumbnailUrl} style={StyleSheet.absoluteFill} radius={14} />
      <Svg style={StyleSheet.absoluteFill} width="100%" height="100%" pointerEvents="none">
        <Defs>
          <LinearGradient id="channelScrim" x1="0" y1="0" x2="0" y2="1">
            <Stop offset="0" stopColor="#100E12" stopOpacity={0} />
            <Stop offset="1" stopColor="#100E12" stopOpacity={0.68} />
          </LinearGradient>
        </Defs>
        <Rect x="0" y="0" width="100%" height="100%" fill="url(#channelScrim)" />
      </Svg>
      <Text style={styles.label}>{meta.label}</Text>
      {showBadge ? <View testID="channel-new-dot" style={styles.badge} /> : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: { paddingHorizontal: 16, gap: 10 },
  tile: {
    width: 86,
    height: 110,
    borderRadius: 14,
    overflow: "hidden",
    backgroundColor: colors.inset,
  },
  dimmed: { opacity: 0.55 },
  label: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 8,
    textAlign: "center",
    fontSize: 11.5,
    fontWeight: "800",
    color: colors.onImage,
  },
  badge: {
    position: "absolute",
    top: 8,
    right: 8,
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.accent,
    borderWidth: 1.5,
    borderColor: colors.onImage,
  },
});
