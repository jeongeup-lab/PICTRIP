import { channelCardsKey } from "@/features/channels/queries";

describe("channelCardsKey", () => {
  it("puts different locations in different keys", () => {
    const a = channelCardsKey("around", { lat: 37.5, lng: 127.0 });
    const b = channelCardsKey("around", { lat: 35.1, lng: 129.0 });
    expect(a).not.toEqual(b);
    expect(a).toEqual(["channel-cards", "around", [37500, 127000]]);
  });

  it("reuses one key for sub-100m GPS jitter", () => {
    const a = channelCardsKey("around", { lat: 37.5, lng: 127.0 });
    const b = channelCardsKey("around", { lat: 37.5001, lng: 127.0001 });
    expect(a).toEqual(b);
  });

  it("uses a null location slot when coords are absent", () => {
    expect(channelCardsKey("hot")).toEqual(["channel-cards", "hot", null]);
  });
});
