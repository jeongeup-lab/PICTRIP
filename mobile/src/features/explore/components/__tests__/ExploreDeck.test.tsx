import renderer, { act } from "react-test-renderer";
import { FlatList } from "react-native";
import {
  ExploreDeck,
  dotWindowStart,
  slideIndexAt,
} from "@/features/explore/components/ExploreDeck";
import { useExploreFeed } from "@/features/explore/queries";
import type { OverseasPost } from "@/features/explore/api";

jest.mock("@/features/explore/queries", () => ({
  useExploreFeed: jest.fn(),
}));
jest.mock("expo-router", () => ({
  useScrollToTop: jest.fn(),
  router: { push: jest.fn() },
}));
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 47, bottom: 34, left: 0, right: 0 }),
}));
jest.mock("@/features/explore/components/CreditSheet", () => ({ CreditSheet: () => null }));

const HEIGHT = 700;
const WIDTH = 390;

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
    matches: [
      {
        contentId: `c${i + 1}`,
        title: `국내 ${i + 1}`,
        regionLabel: "강원 속초시",
        imageUrl: `https://tong.visitkorea.or.kr/${i + 1}_image2_1.jpg`,
        overviewFirst: null,
      },
    ],
  }));
}

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
    isLoading: false,
    isError: false,
    refetch,
    ...over,
  });
}

function hosts(r: renderer.ReactTestRenderer, testID: string) {
  return r.root.findAllByProps({ testID }).filter((n) => typeof n.type === "string");
}

function pressables(r: renderer.ReactTestRenderer, testID: string) {
  return r.root.findAllByProps({ testID }).filter((n) => typeof n.props.onPress === "function");
}

let tree: renderer.ReactTestRenderer | null = null;

afterEach(() => {
  act(() => tree?.unmount());
  tree = null;
  jest.clearAllMocks();
});

async function mount({ measure = true } = {}) {
  await act(async () => {
    tree = renderer.create(<ExploreDeck />);
  });
  if (measure) {
    await act(async () => {
      tree!.root
        .findByProps({ testID: "explore-deck-root" })
        .props.onLayout({ nativeEvent: { layout: { width: WIDTH, height: HEIGHT } } });
    });
  }
  return tree!;
}

async function swipeTo(r: renderer.ReactTestRenderer, index: number) {
  const list = r.root.findAllByType(FlatList)[0];
  await act(async () => {
    list.props.onMomentumScrollEnd({ nativeEvent: { contentOffset: { y: index * HEIGHT } } });
  });
}

describe("slideIndexAt", () => {
  it("rounds the offset onto a slide", () => {
    expect(slideIndexAt(0, 700, 9)).toBe(0);
    expect(slideIndexAt(340, 700, 9)).toBe(0);
    expect(slideIndexAt(360, 700, 9)).toBe(1);
    expect(slideIndexAt(1400, 700, 9)).toBe(2);
  });

  it("never leaves the list", () => {
    expect(slideIndexAt(-200, 700, 9)).toBe(0);
    expect(slideIndexAt(99999, 700, 9)).toBe(8);
    expect(slideIndexAt(100, 0, 9)).toBe(0);
    expect(slideIndexAt(100, 700, 0)).toBe(0);
  });
});

describe("dotWindowStart", () => {
  it("keeps the active dot centred once past the head", () => {
    expect(dotWindowStart(0, 40)).toBe(0);
    expect(dotWindowStart(2, 40)).toBe(0);
    expect(dotWindowStart(10, 40)).toBe(7);
  });

  it("stops sliding at the tail", () => {
    expect(dotWindowStart(39, 40)).toBe(33);
    expect(dotWindowStart(1, 3)).toBe(0);
  });
});

describe("ExploreDeck", () => {
  it("waits for a measured height before mounting slides", async () => {
    setFeed();
    const r = await mount({ measure: false });
    expect(hosts(r, "explore-deck").length).toBe(0);
    await act(async () => {
      r.root
        .findByProps({ testID: "explore-deck-root" })
        .props.onLayout({ nativeEvent: { layout: { width: WIDTH, height: HEIGHT } } });
    });
    expect(r.root.findAllByType(FlatList).length).toBe(1);
  });

  it("renders match tiles straight from the feed page without a second request", async () => {
    setFeed();
    const r = await mount();
    expect(pressables(r, "explore-match-c1").length).toBeGreaterThan(0);
  });

  it("survives a feed page served before the backend inlines matches", async () => {
    setFeed();
    (useExploreFeed as jest.Mock).mockReturnValue({
      ...(useExploreFeed as jest.Mock)(),
      data: {
        pages: [
          {
            seed: "seed-abc",
            items: posts(3).map(({ matches: _matches, ...rest }) => rest),
            nextCursor: null,
            hasMore: false,
          },
        ],
      },
    });
    const r = await mount();
    expect(hosts(r, "explore-match-empty").length).toBeGreaterThan(0);
  });

  it("drops the swipe hint once the user has swiped twice", async () => {
    setFeed();
    const r = await mount();
    expect(hosts(r, "explore-hint").length).toBe(1);
    await swipeTo(r, 1);
    expect(hosts(r, "explore-hint").length).toBe(1);
    await swipeTo(r, 2);
    expect(hosts(r, "explore-hint").length).toBe(0);
  });

  it("opens the grid sheet and jumps the deck to the picked post", async () => {
    setFeed();
    const r = await mount();
    await act(async () => {
      r.root.findByProps({ testID: "explore-grid-open" }).props.onPress();
    });
    expect(hosts(r, "explore-grid-sheet").length).toBe(1);

    const list = r.root.findAllByType(FlatList)[0].instance as {
      scrollToOffset: (arg: { offset: number; animated: boolean }) => void;
    };
    const scrollToOffset = jest.spyOn(list, "scrollToOffset").mockImplementation(() => {});
    await act(async () => {
      pressables(r, "explore-grid-tile")[4].props.onPress();
    });
    expect(scrollToOffset).toHaveBeenCalledWith({ offset: 4 * HEIGHT, animated: false });
    expect(hosts(r, "explore-grid-sheet").length).toBe(0);
  });

  it("fetches the next page as the deck nears its end", async () => {
    setFeed();
    const r = await mount();
    const list = r.root.findAllByType(FlatList)[0];
    await act(async () => list.props.onEndReached());
    expect(fetchNextPage).toHaveBeenCalled();
  });

  it("does not stack page fetches while one is in flight", async () => {
    setFeed({ isFetching: true, isFetchingNextPage: true });
    const r = await mount();
    const list = r.root.findAllByType(FlatList)[0];
    await act(async () => list.props.onEndReached());
    expect(fetchNextPage).not.toHaveBeenCalled();
  });

  it("offers a retry when the feed fails", async () => {
    setFeed({ data: undefined, isError: true, isLoading: false, hasNextPage: false });
    const r = await mount();
    expect(hosts(r, "explore-error").length).toBe(1);
    await act(async () => {
      r.root.findByProps({ testID: "explore-retry" }).props.onPress();
    });
    expect(refetch).toHaveBeenCalled();
  });
});
