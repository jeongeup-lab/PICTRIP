import renderer, { act } from "react-test-renderer";
import { FlatList } from "react-native";
import HomeScreen from "@/app/(tabs)/index";
import { usePostsFeed } from "@/features/feed/posts-queries";
import type { OverseasPost } from "@/features/feed/posts-api";

let seedCounter = 0;
jest.mock("@/lib/seed", () => ({ makeSeed: () => `seed-${(seedCounter += 1)}` }));
jest.mock("expo-router", () => ({
  router: { back: jest.fn(), push: jest.fn() },
}));
jest.mock("react-native-safe-area-context", () => ({
  SafeAreaView: (props: { children?: unknown }) => props.children,
}));
jest.mock("@/features/feed/posts-queries", () => ({ usePostsFeed: jest.fn() }));
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
jest.mock("@/features/feed/components/PostCarousel", () => {
  const React = require("react");
  const { Text } = require("react-native");
  return {
    PostCarousel: ({ post }: { post: { nameKo: string } }) =>
      React.createElement(Text, { testID: "carousel" }, post.nameKo),
  };
});

const usePostsFeedMock = usePostsFeed as jest.Mock;
const { router } = jest.requireMock("expo-router") as { router: { push: jest.Mock } };

function posts(n: number): OverseasPost[] {
  return Array.from({ length: n }, (_, i) => ({
    id: i + 1,
    nameKo: `장소 ${i + 1}`,
    countryCode: "JP",
    countryNameKo: "일본",
    descriptionKo: null,
    imageUrl: `https://upload.wikimedia.org/${i + 1}.jpg`,
    imageAuthor: null,
    imageLicense: null,
    imageLicenseUrl: null,
    imageSourceUrl: `https://commons.wikimedia.org/${i + 1}`,
  }));
}

let fetchNextPage: jest.Mock;
let refetch: jest.Mock;

function setFeed(over: Record<string, unknown> = {}) {
  fetchNextPage = jest.fn();
  refetch = jest.fn();
  usePostsFeedMock.mockReturnValue({
    data: {
      pages: [
        { seed: "seed-abc", items: posts(4), nextCursor: "c1", hasMore: true },
        { seed: "seed-abc", items: posts(2), nextCursor: null, hasMore: false },
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

  it("renders one post carousel per flattened feed item", async () => {
    setFeed();
    const r = await mount();
    expect(hosts(r, "carousel").length).toBe(6);
  });

  it("shows loading skeletons before the first page resolves", async () => {
    setFeed({ data: undefined, isLoading: true });
    const r = await mount();
    expect(hosts(r, "carousel").length).toBe(0);
    expect(r.root.findAllByType(FlatList).length).toBe(0);
  });

  it("shows the error view with a retry that refetches", async () => {
    setFeed({ data: undefined, isError: true });
    const r = await mount();
    expect(hosts(r, "carousel").length).toBe(0);
    await act(async () => {
      r.root.findByProps({ testID: "home-retry" }).props.onPress();
    });
    expect(refetch).toHaveBeenCalled();
  });

  it("renders footer legal links that route to terms, privacy and data-sources", async () => {
    setFeed();
    const r = await mount();
    await act(async () => {
      r.root.findByProps({ testID: "footer-terms" }).props.onPress();
    });
    expect(router.push).toHaveBeenCalledWith("/legal/terms");
    await act(async () => {
      r.root.findByProps({ testID: "footer-privacy" }).props.onPress();
    });
    expect(router.push).toHaveBeenCalledWith("/legal/privacy");
    await act(async () => {
      r.root.findByProps({ testID: "footer-data-source" }).props.onPress();
    });
    expect(router.push).toHaveBeenCalledWith("/legal/data-sources");
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

  it("pull-to-refresh generates a new client seed for a fresh shuffle", async () => {
    setFeed();
    const r = await mount();
    const list = r.root.findAllByType(FlatList)[0];
    const before = usePostsFeedMock.mock.calls.at(-1)?.[0];
    await act(async () => {
      list.props.refreshControl.props.onRefresh();
    });
    const after = usePostsFeedMock.mock.calls.at(-1)?.[0];
    expect(typeof before).toBe("string");
    expect(typeof after).toBe("string");
    expect(after).not.toBe(before);
  });

  it("shows the refresh spinner while a refetch is in flight", async () => {
    setFeed({ isFetching: true });
    const r = await mount();
    const list = r.root.findAllByType(FlatList)[0];
    expect(list.props.refreshControl.props.refreshing).toBe(true);
  });
});
