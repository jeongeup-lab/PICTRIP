import type { ChannelCard, ChannelKey } from "@/features/channels/api";
import type { TravelSpot } from "@/features/travel/api";
import { formatDistance } from "@/lib/distance";

export const HOT_TAG = "붐빔";
export const HIDDEN_TAG = "한산";

export function channelCardTag(key: ChannelKey, card: ChannelCard): string | null {
  if (key === "around") return card.dist !== null ? formatDistance(card.dist) : card.tag;
  if (key === "hot") return card.tag ?? HOT_TAG;
  if (key === "hidden") return card.tag ?? HIDDEN_TAG;
  return card.tag;
}

export function channelCardToSpot(key: ChannelKey, card: ChannelCard): TravelSpot | null {
  if (!card.contentId) return null;
  return {
    contentId: card.contentId,
    title: card.title,
    regionLabel: card.regionLabel,
    imageUrl: card.imageUrl,
    tag: channelCardTag(key, card),
    lat: null,
    lng: null,
  };
}

export function channelCardsToSpots(key: ChannelKey, cards: ChannelCard[]): TravelSpot[] {
  return cards
    .map((card) => channelCardToSpot(key, card))
    .filter((spot): spot is TravelSpot => spot !== null);
}
