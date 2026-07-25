import type { ChannelCard } from "@/features/channels/api";
import {
  channelCardTag,
  channelCardsToSpots,
  HIDDEN_TAG,
  HOT_TAG,
} from "@/features/travel/lib/channel-spots";

const card = (over: Partial<ChannelCard> = {}): ChannelCard => ({
  contentId: "126508",
  title: "무릉계곡",
  regionLabel: "강원도 동해시",
  imageUrl: "https://img.pictrip.org/t1/1620/abc/tong.visitkorea.or.kr/a.jpg",
  dist: null,
  rank: null,
  dday: null,
  line: null,
  tag: null,
  saveable: true,
  ...over,
});

describe("channelCardTag", () => {
  it("renders the around distance from metres", () => {
    expect(channelCardTag("around", card({ dist: 4200 }))).toBe("4.2km");
  });

  it("falls back to the crowding label when hot sends no tag", () => {
    expect(channelCardTag("hot", card())).toBe(HOT_TAG);
    expect(channelCardTag("hidden", card())).toBe(HIDDEN_TAG);
  });

  it("prefers a server-sent tag over the fallback", () => {
    expect(channelCardTag("hidden", card({ tag: "하위 8%" }))).toBe("하위 8%");
  });

  it("has no tag for around without a distance", () => {
    expect(channelCardTag("around", card())).toBeNull();
  });
});

describe("channelCardsToSpots", () => {
  it("passes the backend image url through untouched", () => {
    const [spot] = channelCardsToSpots("hot", [card()]);
    expect(spot.imageUrl).toBe("https://img.pictrip.org/t1/1620/abc/tong.visitkorea.or.kr/a.jpg");
  });

  it("drops cards that carry no contentId to open with", () => {
    expect(channelCardsToSpots("hot", [card({ contentId: null })])).toEqual([]);
  });
});
