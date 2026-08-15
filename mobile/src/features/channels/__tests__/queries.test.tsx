import renderer, { act } from "react-test-renderer";
import { Image } from "expo-image";
import {
  channelCardsKey,
  prefetchChannelCards,
  useSeenChannels,
  useSeenStore,
} from "@/features/channels/queries";
import { getChannelCards } from "@/features/channels/api";
import { loadSeen, saveSeen } from "@/features/channels/lib/seen-store";
import { queryClient } from "@/lib/query-client";

const mockKst = { day: "2026-07-13" };

jest.mock("@/features/channels/lib/kst", () => ({
  todayKst: () => mockKst.day,
}));

jest.mock("@/features/channels/lib/seen-store", () => ({
  loadSeen: jest.fn(async () => []),
  saveSeen: jest.fn(async () => {}),
}));

jest.mock("@/features/channels/api", () => ({
  getChannelCards: jest.fn(),
  getChannels: jest.fn(),
}));

const mockSaveSeen = saveSeen as jest.Mock;
const mockLoadSeen = loadSeen as jest.Mock;

describe("channelCardsKey", () => {
  it("keys by channel alone now that no channel takes coordinates", () => {
    expect(channelCardsKey("hidden")).toEqual(["channel-cards", "hidden"]);
    expect(channelCardsKey("festa")).not.toEqual(channelCardsKey("hidden"));
  });
});

describe("prefetchChannelCards", () => {
  afterEach(() => {
    queryClient.clear();
    jest.restoreAllMocks();
  });

  it("warms the first card image bytes after the cards JSON lands", async () => {
    const prefetch = jest.spyOn(Image, "prefetch").mockResolvedValue(true);
    (getChannelCards as jest.Mock).mockResolvedValue({
      key: "festa",
      label: "Festa",
      cards: [
        { contentId: "1", imageUrl: "https://tong.visitkorea.or.kr/cms/f_image1_1.jpg" },
        { contentId: "2", imageUrl: "https://tong.visitkorea.or.kr/cms/g_image1_1.jpg" },
      ],
    });
    await act(async () => {
      prefetchChannelCards("festa");
    });
    expect(prefetch).toHaveBeenCalledWith(
      "https://img.pictrip.org/tong.visitkorea.or.kr/cms/f_image1_1.jpg",
      { cachePolicy: "memory-disk" },
    );
    expect(prefetch).toHaveBeenCalledTimes(1);
  });

  it("skips cards without an image", async () => {
    const prefetch = jest.spyOn(Image, "prefetch").mockResolvedValue(true);
    prefetch.mockClear();
    (getChannelCards as jest.Mock).mockClear();
    (getChannelCards as jest.Mock).mockResolvedValue({
      key: "snap",
      label: "Snap",
      cards: [{ contentId: null, imageUrl: null }],
    });
    await act(async () => {
      prefetchChannelCards("snap");
    });
    expect(prefetch).not.toHaveBeenCalled();
    expect(getChannelCards).toHaveBeenCalledTimes(1);
  });
});

describe("useSeenChannels day reset", () => {
  let trees: renderer.ReactTestRenderer[] = [];
  const mountHarness = (Harness: () => null) => {
    const tree = renderer.create(<Harness />);
    trees.push(tree);
    return tree;
  };

  beforeEach(() => {
    trees = [];
    useSeenStore.setState({ seen: new Set(), day: null, hydrated: false });
    mockLoadSeen.mockReset();
    mockLoadSeen.mockResolvedValue([]);
    mockSaveSeen.mockClear();
  });

  afterEach(async () => {
    await act(async () => {
      trees.forEach((t) => t.unmount());
    });
  });

  it("drops yesterday's keys and stamps the new day when KST midnight rolls over", async () => {
    let hook: ReturnType<typeof useSeenChannels> | undefined;
    function Harness() {
      hook = useSeenChannels();
      return null;
    }

    mockKst.day = "2026-07-13";
    mockSaveSeen.mockClear();
    await act(async () => {
      mountHarness(Harness);
    });

    await act(async () => {
      hook!.markSeen("pets");
    });
    expect(hook!.seen.has("pets")).toBe(true);
    expect(mockSaveSeen).toHaveBeenLastCalledWith(["pets"], "2026-07-13");

    mockKst.day = "2026-07-14";
    await act(async () => {
      hook!.markSeen("festa");
    });
    expect([...hook!.seen]).toEqual(["festa"]);
    expect(hook!.seen.has("pets")).toBe(false);
    expect(mockSaveSeen).toHaveBeenLastCalledWith(["festa"], "2026-07-14");
  });

  it("shows no seen channels after midnight even without a new markSeen", async () => {
    let hook: ReturnType<typeof useSeenChannels> | undefined;
    function Harness() {
      hook = useSeenChannels();
      return null;
    }

    mockKst.day = "2026-07-13";
    let tree: renderer.ReactTestRenderer;
    await act(async () => {
      tree = mountHarness(Harness);
    });
    await act(async () => {
      hook!.markSeen("pets");
    });
    expect(hook!.seen.has("pets")).toBe(true);

    mockKst.day = "2026-07-14";
    await act(async () => {
      tree!.update(<Harness />);
    });
    expect(hook!.seen.size).toBe(0);
  });

  it("merges a concurrent markSeen instead of overwriting it when hydrate resolves", async () => {
    let resolveLoad: ((keys: string[]) => void) | undefined;
    mockLoadSeen.mockImplementationOnce(
      () =>
        new Promise<string[]>((resolve) => {
          resolveLoad = resolve;
        }),
    );

    mockKst.day = "2026-07-15";
    let hook: ReturnType<typeof useSeenChannels> | undefined;
    function Harness() {
      hook = useSeenChannels();
      return null;
    }
    await act(async () => {
      mountHarness(Harness);
    });

    await act(async () => {
      hook!.markSeen("pets");
    });
    expect(hook!.seen.has("pets")).toBe(true);

    await act(async () => {
      resolveLoad!(["hidden"]);
      await Promise.resolve();
    });

    expect(hook!.seen.has("pets")).toBe(true);
    expect(hook!.seen.has("hidden")).toBe(true);
  });

  it("defers a pre-hydrate markSeen persist and keeps the stored keys once hydrate resolves", async () => {
    let resolveLoad: ((keys: string[]) => void) | undefined;
    mockLoadSeen.mockImplementationOnce(
      () =>
        new Promise<string[]>((resolve) => {
          resolveLoad = resolve;
        }),
    );

    mockKst.day = "2026-07-16";
    let hook: ReturnType<typeof useSeenChannels> | undefined;
    function Harness() {
      hook = useSeenChannels();
      return null;
    }
    await act(async () => {
      mountHarness(Harness);
    });

    await act(async () => {
      hook!.markSeen("pets");
    });
    expect(hook!.seen.has("pets")).toBe(true);
    expect(mockSaveSeen).not.toHaveBeenCalled();

    await act(async () => {
      resolveLoad!(["hidden"]);
      await Promise.resolve();
    });

    expect(hook!.seen.has("pets")).toBe(true);
    expect(hook!.seen.has("hidden")).toBe(true);
    expect(mockSaveSeen).toHaveBeenCalledTimes(1);
    const persisted = new Set(mockSaveSeen.mock.calls[0][0] as string[]);
    expect(persisted.has("pets")).toBe(true);
    expect(persisted.has("hidden")).toBe(true);
  });
});
