import renderer, { act } from "react-test-renderer";
import { StyleSheet } from "react-native";
import { ChannelTiles } from "@/features/channels/components/ChannelTiles";
import { prefetchChannelCards, useChannels, useSeenChannels } from "@/features/channels/queries";
import type { ChannelKey, ChannelMeta } from "@/features/channels/api";

jest.mock("@/features/channels/queries", () => ({
  useChannels: jest.fn(),
  useSeenChannels: jest.fn(),
  prefetchChannelCards: jest.fn(),
}));

const mockChannels = useChannels as jest.Mock;
const mockSeen = useSeenChannels as jest.Mock;
const mockPrefetch = prefetchChannelCards as jest.Mock;

function setChannels(channels: ChannelMeta[]) {
  mockChannels.mockReturnValue({ data: { channels } });
}

function setSeen(keys: ChannelKey[]) {
  mockSeen.mockReturnValue({ seen: new Set<ChannelKey>(keys), markSeen: jest.fn() });
}

async function mount(onOpen: (key: ChannelKey) => void) {
  let r: renderer.ReactTestRenderer;
  await act(async () => {
    r = renderer.create(<ChannelTiles onOpen={onOpen} />);
  });
  return r!;
}

function tiles(r: renderer.ReactTestRenderer) {
  return r.root
    .findAllByProps({ testID: "channel-tile" })
    .filter((n) => typeof n.props.onPress === "function");
}

const meta = (key: ChannelKey, over: Partial<ChannelMeta> = {}): ChannelMeta => ({
  key,
  label: key.charAt(0).toUpperCase() + key.slice(1),
  thumbnailUrl: `https://tong.visitkorea.or.kr/${key}.jpg`,
  available: true,
  ...over,
});

afterEach(() => jest.clearAllMocks());

describe("ChannelTiles", () => {
  it("renders a tile per channel with its English label", async () => {
    setChannels([meta("hidden"), meta("festa"), meta("festa"), meta("spot")]);
    setSeen([]);
    const r = await mount(() => {});
    expect(tiles(r)).toHaveLength(4);
    expect(JSON.stringify(r.toJSON())).toContain("Hidden");
  });

  it("seen tile is dimmed and loses its new badge", async () => {
    setChannels([meta("hidden")]);
    setSeen(["hidden"]);
    const r = await mount(() => {});
    const tile = tiles(r)[0];
    expect(StyleSheet.flatten(tile.props.style).opacity).toBe(0.55);
    expect(r.root.findAllByProps({ testID: "channel-new-dot" })).toHaveLength(0);
  });

  it("available:false tile is dimmed and loses its new badge", async () => {
    setChannels([meta("festa", { available: false })]);
    setSeen([]);
    const r = await mount(() => {});
    const tile = tiles(r)[0];
    expect(StyleSheet.flatten(tile.props.style).opacity).toBe(0.55);
    expect(r.root.findAllByProps({ testID: "channel-new-dot" })).toHaveLength(0);
  });

  it("unseen available tile keeps its new badge", async () => {
    setChannels([meta("hidden")]);
    setSeen([]);
    const r = await mount(() => {});
    expect(r.root.findAllByProps({ testID: "channel-new-dot" }).length).toBeGreaterThan(0);
  });

  it("pressing in a tile prefetches its cards", async () => {
    setChannels([meta("spot"), meta("hidden")]);
    setSeen([]);
    const r = await mount(() => {});
    await act(async () => tiles(r)[1].props.onPressIn());
    expect(mockPrefetch).toHaveBeenCalledWith("hidden");
  });

  it("tapping a tile calls onOpen with its key", async () => {
    setChannels([meta("spot"), meta("hidden")]);
    setSeen([]);
    const onOpen = jest.fn();
    const r = await mount(onOpen);
    const second = tiles(r)[1];
    await act(async () => second.props.onPress());
    expect(onOpen).toHaveBeenCalledWith("hidden");
  });

  it("tapping an available:false tile does not call onOpen", async () => {
    setChannels([meta("festa", { available: false })]);
    setSeen([]);
    const onOpen = jest.fn();
    const r = await mount(onOpen);
    const tile = tiles(r)[0];
    expect(tile.props.disabled).toBe(true);
    await act(async () => {
      if (!tile.props.disabled) tile.props.onPress();
    });
    expect(onOpen).not.toHaveBeenCalled();
  });

  it("tapping an available seen tile still calls onOpen", async () => {
    setChannels([meta("hidden")]);
    setSeen(["hidden"]);
    const onOpen = jest.fn();
    const r = await mount(onOpen);
    const tile = tiles(r)[0];
    expect(tile.props.disabled).toBe(false);
    await act(async () => {
      if (!tile.props.disabled) tile.props.onPress();
    });
    expect(onOpen).toHaveBeenCalledWith("hidden");
  });
});
