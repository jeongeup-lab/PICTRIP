import type { ChannelCard, ChannelKey } from "@/features/channels/api";
import type { TravelSpot } from "@/features/travel/api";
import { formatDistance } from "@/lib/distance";

export function channelCardTag(key: ChannelKey, card: ChannelCard): string | null {
  if (key === "around") return card.dist !== null ? formatDistance(card.dist) : card.tag;
  if (key === "hot" || key === "hidden") return card.rank !== null ? `${card.rank}위` : null;
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
