import { useLocalSearchParams } from "expo-router";
import { StoryViewer } from "@/features/channels/components/StoryViewer";
import type { ChannelKey } from "@/features/channels/api";

export default function ChannelsScreen() {
  const { start } = useLocalSearchParams<{ start?: ChannelKey }>();
  return <StoryViewer start={start ?? "hot"} />;
}
