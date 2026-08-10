import renderer, { act } from "react-test-renderer";
import { FlatList } from "react-native";
import HomeScreen from "@/app/(tabs)/index";
import { useShortsFeed } from "@/features/shorts/queries";
import type { ShortsCardData } from "@/features/shorts/api";
import { queryClient } from "@/lib/query-client";

jest.mock("expo-router", () => ({
  router: { back: jest.fn(), push: jest.fn() },
  useScrollToTop: jest.fn(),
}));
jest.mock("react-native-safe-area-context", () => ({
  SafeAreaView: (props: { children?: unknown }) => props.children,
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
jest.mock("@/features/shorts/queries", () => ({
  useShortsFeed: jest.fn(),
}));
jest.mock("@/features/channels/components/ChannelTiles", () => {
  const React = require("react");
  const { Pressable } = require("react-native");
  return {
    ChannelTiles: ({ onOpen }: { onOpen: (k: string) => void }) =>
      React.createElement(Pressable, {
        testID: "channel-tiles",
        onPress: () => onOpen("hot"),
      }),
  };
});
jest.mock("@/features/shorts/components/ShortsCard", () => {
  const React = require("react");
  const { Pressable } = require("react-native");
  return {
    ShortsCard: ({ short, onOpen }: { short: { videoId: string }; onOpen: (s: unknown) => void }) =>
      React.createElement(Pressable, {
        testID: "shorts-card",
        onPress: () => onOpen(short),
      }),
  };
});
jest.mock("@/features/shorts/components/ShortsPlayerSheet", () => {
  const React = require("react");
  const { View } = require("react-native");
  return {
    ShortsPlayerSheet: ({ short }: { short: { videoId: string } | null }) =>
      short ? React.createElement(View, { testID: "shorts-player-sheet" }) : null,
  };
});

const useShortsFeedMock = useShortsFeed as jest.Mock;
const { router, useScrollToTop } = jest.requireMock("expo-router") as {
  router: { push: jest.Mock };
  useScrollToTop: jest.Mock;
};

function shorts(n: number): ShortsCardData[] {
  return Array.from({ length: n }, (_, i) => ({
    videoId: `vid-${i + 1}`,
    title: `쇼츠 ${i + 1}`,
    channelTitle: `채널 ${i + 1}`,
    thumbnailUrl: `https://i.ytimg.com/vi/vid-${i + 1}/hqdefault.jpg`,
    viewCount: (i + 1) * 1000,
    anchorLabel: "경주",
    spots: [],
  }));
}

let fetchNextPage: jest.Mock;
let refetch: jest.Mock;

function setFeed(over: Record<string, unknown> = {}) {
  fetchNextPage = jest.fn();
  refetch = jest.fn();
  useShortsFeedMock.mockReturnValue({
    data: {
      pages: [
        { items: shorts(4), nextCursor: "4", hasMore: true },
        {
          items: shorts(2).map((s) => ({ ...s, videoId: `${s.videoId}-p2` })),
          nextCursor: null,
          hasMore: false,
        },
      ],
    },
    fetchNextPage,
    hasNextPage: true,
    isFetchingNextPage: false,
    isFetching: false,
    isLoading: false,
    isError: false,
    refetch,
    ...over,
  });
}

function hosts(r: renderer.ReactTestRenderer, testID: string) {
  return r.root.findAllByProps({ testID }).filter((n) => typeof n.type === "string");
}

let tree: renderer.ReactTestRenderer | null = null;

afterEach(() => {
  act(() => tree?.unmount());
  tree = null;
  jest.clearAllMocks();
});

async function mount() {
  await act(async () => {
    tree = renderer.create(<HomeScreen />);
  });
  return tree!;
}

describe("HomeScreen", () => {
  it("renders the PICTRIP wordmark", async () => {
    setFeed();
    const r = await mount();
    expect(r.root.findAllByProps({ children: "PICTRIP" }).length).toBeGreaterThan(0);
  });

  it("renders the channel tiles header and routes to the channel viewer on open", async () => {
    setFeed();
    const r = await mount();
    expect(hosts(r, "channel-tiles").length).toBe(1);
    await act(async () => {
      r.root.findByProps({ testID: "channel-tiles" }).props.onPress();
    });
    expect(router.push).toHaveBeenCalledWith("/channels?start=hot");
  });

  it("renders one shorts card per flattened feed item", async () => {
    setFeed();
    const r = await mount();
    expect(hosts(r, "shorts-card").length).toBe(6);
  });

  it("opens the player sheet when a shorts card is tapped", async () => {
    setFeed();
    const r = await mount();
    expect(hosts(r, "shorts-player-sheet").length).toBe(0);
    await act(async () => {
      r.root.findAllByProps({ testID: "shorts-card" })[0].props.onPress();
    });
    expect(hosts(r, "shorts-player-sheet").length).toBe(1);
  });

  it("shows loading skeletons before the first page resolves", async () => {
    setFeed({ data: undefined, isLoading: true });
    const r = await mount();
    expect(hosts(r, "shorts-card").length).toBe(0);
    expect(r.root.findAllByType(FlatList).length).toBe(0);
  });

  it("shows the error view with a retry that refetches", async () => {
    setFeed({ data: undefined, isError: true });
    const r = await mount();
    expect(hosts(r, "shorts-card").length).toBe(0);
    await act(async () => {
      r.root.findByProps({ testID: "home-retry" }).props.onPress();
    });
    expect(refetch).toHaveBeenCalled();
  });

  it("renders no legal footer under the feed", async () => {
    setFeed();
    const r = await mount();
    expect(hosts(r, "footer-terms").length).toBe(0);
    expect(hosts(r, "footer-privacy").length).toBe(0);
    expect(hosts(r, "footer-data-source").length).toBe(0);
  });

  it("fetches the next page when the list end is reached", async () => {
    setFeed();
    const r = await mount();
    const list = r.root.findAllByType(FlatList)[0];
    await act(async () => {
      list.props.onEndReached();
    });
    expect(fetchNextPage).toHaveBeenCalled();
  });

  it("does not fetch the next page while one is already loading", async () => {
    setFeed({ isFetchingNextPage: true, isFetching: true });
    const r = await mount();
    const list = r.root.findAllByType(FlatList)[0];
    await act(async () => {
      list.props.onEndReached();
    });
    expect(fetchNextPage).not.toHaveBeenCalled();
  });

  it("pull-to-refresh invalidates the shorts query", async () => {
    const invalidate = jest.spyOn(queryClient, "invalidateQueries");
    setFeed();
    const r = await mount();
    const list = r.root.findAllByType(FlatList)[0];
    await act(async () => {
      list.props.refreshControl.props.onRefresh();
    });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["shorts"] });
    invalidate.mockRestore();
  });

  it("shows the refresh spinner while a refetch is in flight", async () => {
    setFeed({ isFetching: true });
    const r = await mount();
    const list = r.root.findAllByType(FlatList)[0];
    expect(list.props.refreshControl.props.refreshing).toBe(true);
  });

  it("wires the feed list into the tab re-tap scroll-to-top hook", async () => {
    setFeed();
    await mount();
    expect(useScrollToTop).toHaveBeenCalled();
  });
});
