import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { prefetchChannelCards, useChannels, useSeenChannels } from "@/features/channels/queries";
import type { ChannelCoords, ChannelKey, ChannelMeta } from "@/features/channels/api";
import { colors, radii, spacing } from "@/constants/theme";

interface Props {
  coords: ChannelCoords | null;
  onOpen: (key: ChannelKey) => void;
}

export function ChannelChips({ coords, onOpen }: Props) {
  const { data } = useChannels(coords);
  const { seen } = useSeenChannels();
  const channels = data?.channels ?? [];
  if (channels.length === 0) return null;

  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.track}
    >
      {channels.map((meta) => (
        <ChannelChip
          key={meta.key}
          meta={meta}
          coords={coords}
          seen={seen.has(meta.key)}
          onOpen={onOpen}
        />
      ))}
    </ScrollView>
  );
}

function ChannelChip({
  meta,
  coords,
  seen,
  onOpen,
}: {
  meta: ChannelMeta;
  coords: ChannelCoords | null;
  seen: boolean;
  onOpen: (key: ChannelKey) => void;
}) {
  return (
    <Pressable
      testID="channel-chip"
      accessibilityRole="button"
      accessibilityLabel={`${meta.label} 채널 열기`}
      disabled={!meta.available}
      onPressIn={() => prefetchChannelCards(meta.key, coords)}
      onPress={() => onOpen(meta.key)}
      style={({ pressed }) => [
        styles.chip,
        !meta.available && styles.dimmed,
        pressed && styles.pressed,
      ]}
    >
      <Text style={styles.label}>{meta.label}</Text>
      {!seen && meta.available ? <View testID="channel-new-dot" style={styles.dot} /> : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  track: { gap: 8, paddingHorizontal: spacing.lg },
  chip: {
    height: 34,
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: 14,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.fill,
  },
  dimmed: { opacity: 0.45 },
  label: { fontSize: 12.5, fontWeight: "800", letterSpacing: 0.2, color: colors.sec },
  dot: { width: 5, height: 5, borderRadius: 3, backgroundColor: colors.accent },
  pressed: { opacity: 0.7 },
});
