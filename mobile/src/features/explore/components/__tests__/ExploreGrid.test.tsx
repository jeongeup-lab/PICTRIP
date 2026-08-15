import renderer, { act } from "react-test-renderer";
import { FlatList } from "react-native";
import { ExploreGrid } from "@/features/explore/components/ExploreGrid";
import { useExploreFeed } from "@/features/explore/queries";
import type { OverseasPost } from "@/features/feed/posts-api";

jest.mock("@/features/explore/queries", () => ({ useExploreFeed: jest.fn() }));
jest.mock("expo-router", () => ({ useScrollToTop: jest.fn() }));
jest.mock("@/features/feed/components/PostCarousel", () => {
  const React = require("react");
  const { Text } = require("react-native");
  return {
    PostCarousel: ({ post }: { post: { nameKo: string } }) =>
      React.createElement(Text, { testID: "carousel" }, post.nameKo),
  };
});

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

const { useScrollToTop } = jest.requireMock("expo-router") as { useScrollToTop: jest.Mock };

let fetchNextPage: jest.Mock;
let refetch: jest.Mock;

function setFeed(over: Record<string, unknown> = {}) {
  fetchNextPage = jest.fn();
  refetch = jest.fn();
  (useExploreFeed as jest.Mock).mockReturnValue({
    data: { pages: [{ seed: "seed-abc", items: posts(9), nextCursor: "c1", hasMore: true }] },
    fetchNextPage,
    hasNextPage: true,
    isFetchingNextPage: false,
    isFetching: false,
    isRefetching: false,
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
    tree = renderer.create(<ExploreGrid />);
  });
  return tree!;
}

describe("ExploreGrid", () => {
  it("renders a tile per item with no text label", async () => {
    setFeed();
    const r = await mount();
    expect(hosts(r, "explore-tile").length).toBe(9);
    expect(hosts(r, "carousel").length).toBe(0);
  });

  it("opens the post modal with a carousel when a tile is tapped", async () => {
    setFeed();
    const r = await mount();
    await act(async () => {
      r.root.findAllByProps({ testID: "explore-tile" })[0].props.onPress();
    });
    const carousel = hosts(r, "carousel");
    expect(carousel.length).toBe(1);
    expect(carousel[0].props.children).toBe("장소 1");
  });

  it("closes the modal via the close button", async () => {
    setFeed();
    const r = await mount();
    await act(async () => {
      r.root.findAllByProps({ testID: "explore-tile" })[0].props.onPress();
    });
    await act(async () => {
      r.root.findByProps({ testID: "post-modal-close" }).props.onPress();
    });
    expect(hosts(r, "carousel").length).toBe(0);
  });

  it("closes the modal when the empty space around the post is tapped", async () => {
    setFeed();
    const r = await mount();
    await act(async () => {
      r.root.findAllByProps({ testID: "explore-tile" })[0].props.onPress();
    });
    await act(async () => {
      r.root.findByProps({ testID: "post-modal-backdrop" }).props.onPress();
    });
    expect(hosts(r, "carousel").length).toBe(0);
  });

  it("keeps the modal open when the post itself is tapped", async () => {
    setFeed();
    const r = await mount();
    await act(async () => {
      r.root.findAllByProps({ testID: "explore-tile" })[0].props.onPress();
    });
    const sheet = r.root.findByProps({ testID: "post-modal-sheet" });
    expect(sheet.props.onStartShouldSetResponder()).toBe(true);
    expect(hosts(r, "carousel").length).toBe(1);
  });

  it("wires the grid list into the tab re-tap scroll-to-top hook", async () => {
    setFeed();
    const r = await mount();
    expect(useScrollToTop).toHaveBeenCalled();
    const ref = useScrollToTop.mock.calls.at(-1)?.[0] as {
      current: { scrollToOffset?: unknown } | null;
    };
    expect(ref.current).toBe(r.root.findAllByType(FlatList)[0].instance);
    expect(typeof ref.current?.scrollToOffset).toBe("function");
  });

  it("pull-to-refresh hands useExploreFeed a fresh seed to reshuffle", async () => {
    setFeed();
    const r = await mount();
    const list = r.root.findAllByType(FlatList)[0];
    const seedBefore = (useExploreFeed as jest.Mock).mock.calls.at(-1)![0];
    await act(async () => {
      list.props.refreshControl.props.onRefresh();
    });
    const seedAfter = (useExploreFeed as jest.Mock).mock.calls.at(-1)![0];
    expect(typeof seedBefore).toBe("string");
    expect(typeof seedAfter).toBe("string");
    expect(seedAfter).not.toBe(seedBefore);
  });

  it("renders the trailing leftover tiles on the last page", async () => {
    setFeed({
      data: { pages: [{ seed: "seed-abc", items: posts(10), nextCursor: null, hasMore: false }] },
      hasNextPage: false,
    });
    const r = await mount();
    expect(hosts(r, "explore-tile").length).toBe(10);
  });

  it("drops the leftover while more pages remain", async () => {
    setFeed({
      data: { pages: [{ seed: "seed-abc", items: posts(10), nextCursor: "c1", hasMore: true }] },
      hasNextPage: true,
    });
    const r = await mount();
    expect(hosts(r, "explore-tile").length).toBe(9);
  });

  it("shows the refresh spinner while a seed refetch keeps previous items", async () => {
    setFeed({ isFetching: true, isLoading: false, isFetchingNextPage: false });
    const r = await mount();
    const list = r.root.findAllByType(FlatList)[0];
    expect(list.props.refreshControl.props.refreshing).toBe(true);
  });

  it("hides the refresh spinner during the initial load", async () => {
    setFeed({ isFetching: true, isLoading: true, isFetchingNextPage: false });
    const r = await mount();
    const list = r.root.findAllByType(FlatList)[0];
    expect(list.props.refreshControl.props.refreshing).toBe(false);
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

  it("does not fetch the next page during a seed refresh", async () => {
    setFeed({ isFetching: true, isLoading: false, isFetchingNextPage: false });
    const r = await mount();
    const list = r.root.findAllByType(FlatList)[0];
    await act(async () => {
      list.props.onEndReached();
    });
    expect(fetchNextPage).not.toHaveBeenCalled();
  });
});
