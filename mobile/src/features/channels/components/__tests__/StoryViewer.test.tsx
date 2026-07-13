import React from "react";
import renderer, { act } from "react-test-renderer";
import { router } from "expo-router";
import { StoryViewer } from "@/features/channels/components/StoryViewer";
import { useChannels, useChannelCards, useSeenChannels } from "@/features/channels/queries";
import { useSaveOptimistic } from "@/features/saved/hooks/use-save-optimistic";
import {
  getCurrentCoords,
  getPermissionStatus,
  requestPermission,
} from "@/features/map/usecases/request-location";
import type { ChannelCard, ChannelKey, ChannelMeta } from "@/features/channels/api";

jest.mock("expo-router", () => ({ router: { back: jest.fn(), push: jest.fn() } }));
jest.mock("@/features/channels/queries", () => ({
  useChannels: jest.fn(),
  useChannelCards: jest.fn(),
  useSeenChannels: jest.fn(),
}));
jest.mock("@/features/saved/hooks/use-save-optimistic", () => ({ useSaveOptimistic: jest.fn() }));
jest.mock("@/features/map/usecases/request-location", () => ({
  getPermissionStatus: jest.fn(),
  getCurrentCoords: jest.fn(),
  requestPermission: jest.fn(),
}));
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));

const mockMarkSeen = jest.fn();
let cardsByKey: Partial<Record<ChannelKey, ChannelCard[]>> = {};

const meta = (key: ChannelKey, label: string): ChannelMeta => ({
  key,
  label,
  thumbnailUrl: null,
  available: true,
});

const card = (over: Partial<ChannelCard> = {}): ChannelCard => ({
  contentId: "1",
  title: "T",
  regionLabel: "지역",
  imageUrl: null,
  dist: null,
  rank: null,
  dday: null,
  line: null,
  tag: null,
  saveable: true,
  ...over,
});

function setChannels(channels: ChannelMeta[]) {
  (useChannels as jest.Mock).mockReturnValue({ data: { channels } });
}

beforeEach(() => {
  cardsByKey = {};
  (useChannelCards as jest.Mock).mockImplementation((key: ChannelKey) => {
    const cards = cardsByKey[key];
    return { data: cards ? { key, label: key, cards } : undefined };
  });
  (useSeenChannels as jest.Mock).mockReturnValue({ seen: new Set(), markSeen: mockMarkSeen });
  (useSaveOptimistic as jest.Mock).mockReturnValue({ saved: false, toggle: jest.fn() });
  (getPermissionStatus as jest.Mock).mockResolvedValue("granted");
  (getCurrentCoords as jest.Mock).mockResolvedValue(null);
  (requestPermission as jest.Mock).mockResolvedValue("granted");
});

afterEach(() => jest.clearAllMocks());

async function mount(start: ChannelKey) {
  let r: renderer.ReactTestRenderer;
  await act(async () => {
    r = renderer.create(<StoryViewer start={start} />);
  });
  return r!;
}

const title = (r: renderer.ReactTestRenderer) =>
  r.root.findByProps({ testID: "story-card-title" }).props.children as string;

const tap = async (r: renderer.ReactTestRenderer, side: "right" | "left") => {
  await act(async () => {
    r.root.findByProps({ testID: `story-tap-${side}` }).props.onPress();
  });
};

const saveIconName = (r: renderer.ReactTestRenderer) =>
  r.root.findByProps({ testID: "story-save" }).findByProps({ size: 20 }).props.name as string;

describe("StoryViewer", () => {
  it("renders progress segments equal to card count and the English channel title", async () => {
    setChannels([meta("hot", "Hot"), meta("hidden", "Hidden")]);
    cardsByKey.hot = [card({ title: "A" }), card({ title: "B" })];
    const r = await mount("hot");
    const segs = r.root
      .findAllByProps({ testID: "story-progress-seg" })
      .filter((n) => typeof n.type === "string");
    expect(segs).toHaveLength(2);
    expect(JSON.stringify(r.toJSON())).toContain("Hot");
    expect(title(r)).toBe("A");
  });

  it("right tap advances the card, left tap goes back", async () => {
    setChannels([meta("hot", "Hot")]);
    cardsByKey.hot = [card({ title: "A" }), card({ title: "B" })];
    const r = await mount("hot");
    await tap(r, "right");
    expect(title(r)).toBe("B");
    await tap(r, "left");
    expect(title(r)).toBe("A");
  });

  it("tapping past the last card of the last channel closes the viewer and marks it seen", async () => {
    setChannels([meta("hot", "Hot"), meta("hidden", "Hidden")]);
    cardsByKey.hidden = [card({ title: "H1" }), card({ title: "H2" })];
    const r = await mount("hidden");
    await tap(r, "right");
    await tap(r, "right");
    expect(mockMarkSeen).toHaveBeenCalledWith("hidden");
    expect(router.back).toHaveBeenCalled();
  });

  it("skips unavailable channels: past the last available channel closes without entering a locked one", async () => {
    setChannels([meta("hot", "Hot"), { ...meta("hidden", "Hidden"), available: false }]);
    cardsByKey.hot = [card({ title: "A" }), card({ title: "B" })];
    cardsByKey.hidden = [card({ title: "H1" })];
    const r = await mount("hot");
    await tap(r, "right");
    await tap(r, "right");
    expect(mockMarkSeen).toHaveBeenCalledWith("hot");
    expect(mockMarkSeen).not.toHaveBeenCalledWith("hidden");
    expect(router.back).toHaveBeenCalled();
    expect(JSON.stringify(r.toJSON())).not.toContain("Hidden");
  });

  it("advancing past the last card moves to the next channel and marks the current seen", async () => {
    setChannels([meta("hot", "Hot"), meta("hidden", "Hidden")]);
    cardsByKey.hot = [card({ title: "A" }), card({ title: "B" })];
    cardsByKey.hidden = [card({ title: "H1" }), card({ title: "H2" })];
    const r = await mount("hot");
    await tap(r, "right");
    await tap(r, "right");
    expect(mockMarkSeen).toHaveBeenCalledWith("hot");
    expect(title(r)).toBe("H1");
  });

  it("ignores a channel-advancing tap while the current channel's cards are loading", async () => {
    setChannels([meta("hot", "Hot"), meta("hidden", "Hidden")]);
    (useChannelCards as jest.Mock).mockReturnValue({ data: undefined, isLoading: true });
    const r = await mount("hot");
    await tap(r, "right");
    expect(mockMarkSeen).not.toHaveBeenCalled();
    expect(JSON.stringify(r.toJSON())).toContain("Hot");
    expect(JSON.stringify(r.toJSON())).not.toContain("Hidden");
  });

  it("blocks channel navigation and renders an error card when the cards fail to load", async () => {
    setChannels([meta("hot", "Hot"), meta("hidden", "Hidden")]);
    (useChannelCards as jest.Mock).mockReturnValue({ data: undefined, isError: true });
    const r = await mount("hot");
    expect(JSON.stringify(r.toJSON())).toContain("채널을 불러오지 못했어요");
    expect(r.root.findAllByProps({ testID: "story-tap-right" })).toHaveLength(0);
    expect(mockMarkSeen).not.toHaveBeenCalled();
    expect(JSON.stringify(r.toJSON())).not.toContain("Hidden");
  });

  it("advances to the next channel and marks it seen once the cards have loaded", async () => {
    setChannels([meta("hot", "Hot"), meta("hidden", "Hidden")]);
    cardsByKey.hot = [card({ title: "A" })];
    cardsByKey.hidden = [card({ title: "H1" })];
    const r = await mount("hot");
    await tap(r, "right");
    expect(mockMarkSeen).toHaveBeenCalledWith("hot");
    expect(title(r)).toBe("H1");
  });

  it("hides the save and detail buttons on a non-saveable snap card", async () => {
    setChannels([meta("snap", "Snap")]);
    cardsByKey.snap = [card({ title: "S1", saveable: false, contentId: null })];
    const r = await mount("snap");
    expect(r.root.findAllByProps({ testID: "story-save" })).toHaveLength(0);
    expect(r.root.findAllByProps({ testID: "story-detail" })).toHaveLength(0);
  });

  it("detail button closes the viewer then pushes the spot detail route", async () => {
    setChannels([meta("hot", "Hot")]);
    cardsByKey.hot = [card({ title: "A", contentId: "777" })];
    const order: string[] = [];
    (router.back as jest.Mock).mockImplementation(() => order.push("back"));
    (router.push as jest.Mock).mockImplementation(() => order.push("push"));
    const r = await mount("hot");
    await act(async () => {
      r.root.findByProps({ testID: "story-detail" }).props.onPress();
    });
    expect(router.push).toHaveBeenCalledWith("/spots/777");
    expect(order).toEqual(["back", "push"]);
  });

  it("shows the permission primer for the around channel when permission is not granted", async () => {
    setChannels([meta("around", "Around")]);
    cardsByKey.around = [card({ title: "AR" })];
    (getPermissionStatus as jest.Mock).mockResolvedValue("denied");
    const r = await mount("around");
    await act(async () => {});
    expect(JSON.stringify(r.toJSON())).toContain("위치 허용하기");
    expect(getCurrentCoords).not.toHaveBeenCalled();
  });

  it("falls back to the permission primer when granted coords resolve null", async () => {
    setChannels([meta("around", "Around")]);
    cardsByKey.around = [card({ title: "AR" })];
    (getPermissionStatus as jest.Mock).mockResolvedValue("granted");
    (getCurrentCoords as jest.Mock).mockResolvedValue(null);
    const r = await mount("around");
    await act(async () => {});
    expect(getCurrentCoords).toHaveBeenCalled();
    expect(JSON.stringify(r.toJSON())).toContain("위치 허용하기");
  });

  it("reads current coords for the around channel when permission is already granted", async () => {
    setChannels([meta("around", "Around")]);
    cardsByKey.around = [card({ title: "AR" })];
    (getPermissionStatus as jest.Mock).mockResolvedValue("granted");
    (getCurrentCoords as jest.Mock).mockResolvedValue({ lat: 37.5, lng: 127 });
    const r = await mount("around");
    await act(async () => {});
    expect(getCurrentCoords).toHaveBeenCalled();
    expect(title(r)).toBe("AR");
  });

  it("does not leak an optimistic save from one card onto the next", async () => {
    setChannels([meta("hot", "Hot")]);
    cardsByKey.hot = [card({ title: "A", contentId: "a1" }), card({ title: "B", contentId: "b1" })];
    (useSaveOptimistic as jest.Mock).mockImplementation(() => {
      const [saved, setSaved] = React.useState(false);
      return { saved, toggle: async () => setSaved((s) => !s) };
    });
    const r = await mount("hot");
    await act(async () => {
      r.root.findByProps({ testID: "story-save" }).props.onPress();
    });
    expect(saveIconName(r)).toBe("bookmark-fill");
    await tap(r, "right");
    expect(title(r)).toBe("B");
    expect(saveIconName(r)).toBe("bookmark");
  });

  it("reconciles to the start channel once channels load on a cold entry", async () => {
    (useChannels as jest.Mock).mockReturnValue({ data: undefined });
    cardsByKey.hot = [card({ title: "A" })];
    cardsByKey.hidden = [card({ title: "H1" })];
    const r = await mount("hidden");
    await act(async () => {
      setChannels([meta("hot", "Hot"), meta("hidden", "Hidden")]);
      r.update(<StoryViewer start="hidden" />);
    });
    expect(JSON.stringify(r.toJSON())).toContain("Hidden");
    expect(title(r)).toBe("H1");
  });

  it("renders a closeable fallback instead of null when channels are empty or still loading", async () => {
    (useChannels as jest.Mock).mockReturnValue({ data: undefined });
    const r = await mount("hot");
    expect(r.toJSON()).not.toBeNull();
    const closeBtn = r.root.findByProps({ testID: "story-empty-close" });
    await act(async () => {
      closeBtn.props.onPress();
    });
    expect(router.back).toHaveBeenCalled();
  });

  it("shows an error (not an endless spinner) when the channel list fails", async () => {
    (useChannels as jest.Mock).mockReturnValue({ data: undefined, isError: true });
    const r = await mount("hot");
    expect(JSON.stringify(r.toJSON())).toContain("채널을 불러오지 못했어요");
    r.root.findByProps({ testID: "story-empty-close" });
  });

  it("shows a no-channels message (not a spinner) when loaded but none are available", async () => {
    (useChannels as jest.Mock).mockReturnValue({ data: { channels: [] } });
    const r = await mount("hot");
    expect(JSON.stringify(r.toJSON())).toContain("지금은 열 수 있는 채널이 없어요");
    r.root.findByProps({ testID: "story-empty-close" });
  });

  it("does not override manual navigation after the initial start resolves", async () => {
    (useChannels as jest.Mock).mockReturnValue({ data: undefined });
    cardsByKey.hot = [card({ title: "A" })];
    cardsByKey.hidden = [card({ title: "H1" })];
    const r = await mount("hidden");
    await act(async () => {
      setChannels([meta("hot", "Hot"), meta("hidden", "Hidden")]);
      r.update(<StoryViewer start="hidden" />);
    });
    expect(title(r)).toBe("H1");
    await tap(r, "left");
    expect(title(r)).toBe("A");
    await act(async () => {
      r.update(<StoryViewer start="hidden" />);
    });
    expect(title(r)).toBe("A");
  });
});
