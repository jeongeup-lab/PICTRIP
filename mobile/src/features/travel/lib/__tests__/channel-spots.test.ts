import type { ChannelCard } from "@/features/channels/api";
import { channelCardTag, channelCardsToSpots } from "@/features/travel/lib/channel-spots";

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

  it("badges hot and hidden with the rank the server sorted them by", () => {
    expect(channelCardTag("hot", card({ rank: 1 }))).toBe("1위");
    expect(channelCardTag("hidden", card({ rank: 3 }))).toBe("3위");
  });

  it("shows no badge rather than a made-up crowding label when the rank is missing", () => {
    expect(channelCardTag("hot", card())).toBeNull();
    expect(channelCardTag("hidden", card())).toBeNull();
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
