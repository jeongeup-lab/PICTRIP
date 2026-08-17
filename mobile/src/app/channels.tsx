import { useLocalSearchParams } from "expo-router";
import { StoryViewer } from "@/features/channels/components/StoryViewer";
import type { ChannelKey } from "@/features/channels/api";

const CHANNEL_KEYS: readonly ChannelKey[] = ["spot", "cafe", "food", "festa", "hidden"];

export default function ChannelsScreen() {
  const { start } = useLocalSearchParams<{ start?: string }>();
  const safeStart: ChannelKey = CHANNEL_KEYS.includes(start as ChannelKey)
    ? (start as ChannelKey)
    : "spot";
  return <StoryViewer start={safeStart} />;
}
