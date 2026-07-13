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
});
