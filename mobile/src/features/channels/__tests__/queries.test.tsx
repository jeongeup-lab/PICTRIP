import renderer, { act } from "react-test-renderer";
import { channelCardsKey, useSeenChannels } from "@/features/channels/queries";
import { saveSeen } from "@/features/channels/lib/seen-store";

const mockKst = { day: "2026-07-13" };

jest.mock("@/features/channels/lib/kst", () => ({
  todayKst: () => mockKst.day,
}));

jest.mock("@/features/channels/lib/seen-store", () => ({
  loadSeen: jest.fn(async () => []),
  saveSeen: jest.fn(async () => {}),
}));

const mockSaveSeen = saveSeen as jest.Mock;

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

describe("useSeenChannels day reset", () => {
  it("drops yesterday's keys and stamps the new day when KST midnight rolls over", async () => {
    let hook: ReturnType<typeof useSeenChannels> | undefined;
    function Harness() {
      hook = useSeenChannels();
      return null;
    }

    mockKst.day = "2026-07-13";
    mockSaveSeen.mockClear();
    await act(async () => {
      renderer.create(<Harness />);
    });

    await act(async () => {
      hook!.markSeen("hot");
    });
    expect(hook!.seen.has("hot")).toBe(true);
    expect(mockSaveSeen).toHaveBeenLastCalledWith(["hot"], "2026-07-13");

    mockKst.day = "2026-07-14";
    await act(async () => {
      hook!.markSeen("festa");
    });
    expect([...hook!.seen]).toEqual(["festa"]);
    expect(hook!.seen.has("hot")).toBe(false);
    expect(mockSaveSeen).toHaveBeenLastCalledWith(["festa"], "2026-07-14");
  });
});
