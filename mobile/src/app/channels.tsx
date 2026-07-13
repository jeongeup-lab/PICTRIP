import { useLocalSearchParams } from "expo-router";
import { StoryViewer } from "@/features/channels/components/StoryViewer";
import type { ChannelKey } from "@/features/channels/api";

const CHANNEL_KEYS: readonly ChannelKey[] = ["around", "hot", "hidden", "festa", "pets", "snap"];

export default function ChannelsScreen() {
  const { start } = useLocalSearchParams<{ start?: string }>();
  const safeStart: ChannelKey = CHANNEL_KEYS.includes(start as ChannelKey)
    ? (start as ChannelKey)
    : "hot";
  return <StoryViewer start={safeStart} />;
}
