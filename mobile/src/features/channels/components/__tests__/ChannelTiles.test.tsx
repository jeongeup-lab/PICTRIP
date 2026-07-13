import renderer, { act } from "react-test-renderer";
import { StyleSheet } from "react-native";
import { ChannelTiles } from "@/features/channels/components/ChannelTiles";
import { useChannels, useSeenChannels } from "@/features/channels/queries";
import type { ChannelKey, ChannelMeta } from "@/features/channels/api";

jest.mock("@/features/channels/queries", () => ({
  useChannels: jest.fn(),
  useSeenChannels: jest.fn(),
}));

const mockChannels = useChannels as jest.Mock;
const mockSeen = useSeenChannels as jest.Mock;

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
  thumbnailUrl: key === "around" ? null : `https://tong.visitkorea.or.kr/${key}.jpg`,
  available: true,
  ...over,
});

afterEach(() => jest.clearAllMocks());

describe("ChannelTiles", () => {
  it("renders a tile per channel with its English label", async () => {
    setChannels([meta("around"), meta("hot"), meta("hidden"), meta("festa"), meta("pets")]);
    setSeen([]);
    const r = await mount(() => {});
    expect(tiles(r)).toHaveLength(5);
    expect(JSON.stringify(r.toJSON())).toContain("Hot");
  });

  it("around tile renders the pin icon instead of a photo", async () => {
    setChannels([meta("around")]);
    setSeen([]);
    const r = await mount(() => {});
    expect(r.root.findAllByProps({ name: "map-pin" }).length).toBeGreaterThan(0);
  });

  it("seen tile is dimmed and loses its new badge", async () => {
    setChannels([meta("hot")]);
    setSeen(["hot"]);
    const r = await mount(() => {});
    const tile = tiles(r)[0];
    expect(StyleSheet.flatten(tile.props.style).opacity).toBe(0.55);
    expect(r.root.findAllByProps({ testID: "channel-new-dot" })).toHaveLength(0);
  });

  it("available:false tile is dimmed and loses its new badge", async () => {
    setChannels([meta("pets", { available: false })]);
    setSeen([]);
    const r = await mount(() => {});
    const tile = tiles(r)[0];
    expect(StyleSheet.flatten(tile.props.style).opacity).toBe(0.55);
    expect(r.root.findAllByProps({ testID: "channel-new-dot" })).toHaveLength(0);
  });

  it("unseen available tile keeps its new badge", async () => {
    setChannels([meta("hot")]);
    setSeen([]);
    const r = await mount(() => {});
    expect(r.root.findAllByProps({ testID: "channel-new-dot" }).length).toBeGreaterThan(0);
  });

  it("tapping a tile calls onOpen with its key", async () => {
    setChannels([meta("around"), meta("hot")]);
    setSeen([]);
    const onOpen = jest.fn();
    const r = await mount(onOpen);
    const hot = tiles(r)[1];
    await act(async () => hot.props.onPress());
    expect(onOpen).toHaveBeenCalledWith("hot");
  });
});
