import renderer, { act } from "react-test-renderer";
import { channelCardsKey, useSeenChannels, useSeenStore } from "@/features/channels/queries";
import { loadSeen, saveSeen } from "@/features/channels/lib/seen-store";

const mockKst = { day: "2026-07-13" };

jest.mock("@/features/channels/lib/kst", () => ({
  todayKst: () => mockKst.day,
}));

jest.mock("@/features/channels/lib/seen-store", () => ({
  loadSeen: jest.fn(async () => []),
  saveSeen: jest.fn(async () => {}),
}));

const mockSaveSeen = saveSeen as jest.Mock;
const mockLoadSeen = loadSeen as jest.Mock;

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
      hook!.markSeen("hot");
    });
    expect(hook!.seen.has("hot")).toBe(true);

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
      hook!.markSeen("hot");
    });
    expect(hook!.seen.has("hot")).toBe(true);

    await act(async () => {
      resolveLoad!(["hidden"]);
      await Promise.resolve();
    });

    expect(hook!.seen.has("hot")).toBe(true);
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
      hook!.markSeen("hot");
    });
    expect(hook!.seen.has("hot")).toBe(true);
    expect(mockSaveSeen).not.toHaveBeenCalled();

    await act(async () => {
      resolveLoad!(["hidden"]);
      await Promise.resolve();
    });

    expect(hook!.seen.has("hot")).toBe(true);
    expect(hook!.seen.has("hidden")).toBe(true);
    expect(mockSaveSeen).toHaveBeenCalledTimes(1);
    const persisted = new Set(mockSaveSeen.mock.calls[0][0] as string[]);
    expect(persisted.has("hot")).toBe(true);
    expect(persisted.has("hidden")).toBe(true);
  });
});
