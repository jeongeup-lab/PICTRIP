import renderer, { act } from "react-test-renderer";
import { Dimensions, FlatList, StyleSheet, type ViewStyle } from "react-native";
import { Image } from "expo-image";
import { router } from "expo-router";
import { PostCarousel } from "@/features/feed/components/PostCarousel";
import { MATCH_EMPTY_TEXT } from "@/features/feed/components/PostSlide";
import { useMatches } from "@/features/feed/posts-queries";
import { useSaveOptimistic } from "@/features/saved/hooks/use-save-optimistic";
import type { MatchCard, OverseasPost } from "@/features/feed/posts-api";
import { colors } from "@/constants/theme";

jest.mock("expo-router", () => ({ router: { push: jest.fn() } }));
jest.mock("@/features/feed/posts-queries", () => ({ useMatches: jest.fn() }));
jest.mock("@/features/saved/hooks/use-save-optimistic", () => ({ useSaveOptimistic: jest.fn() }));
jest.mock("@/features/spots/queries", () => ({ prefetchSpot: jest.fn() }));
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));

const post: OverseasPost = {
  id: 7,
  nameKo: "도쿄 타워",
  countryCode: "JP",
  countryNameKo: "일본",
  descriptionKo: "도쿄의 상징적인 전망 타워",
  imageUrl: "https://upload.wikimedia.org/x.jpg",
  imageAuthor: "김작가",
  imageLicense: "CC BY-SA 4.0",
  imageLicenseUrl: "https://creativecommons.org/licenses/by-sa/4.0",
  imageSourceUrl: "https://commons.wikimedia.org/wiki/File:x.jpg",
};

const match = (over: Partial<MatchCard> = {}): MatchCard => ({
  contentId: "100",
  title: "남산 서울타워",
  regionLabel: "서울 용산구",
  imageUrl: "https://tong.visitkorea.or.kr/x.jpg",
  overviewFirst: "서울의 전망 명소",
  ...over,
});

function setMatches(matches: MatchCard[] | undefined) {
  (useMatches as jest.Mock).mockReturnValue({
    data: matches ? { overseasId: 7, matches } : undefined,
  });
}

const text = (r: renderer.ReactTestRenderer) => JSON.stringify(r.toJSON());

const rendered = (r: renderer.ReactTestRenderer, testID: string) =>
  text(r).split(`"testID":"${testID}"`).length - 1;

const CARD_WIDTH = Dimensions.get("window").width - 32;

const activeDot = (r: renderer.ReactTestRenderer) =>
  r.root
    .findAllByProps({ testID: "carousel-dot" })
    .filter((n) => typeof n.type === "string")
    .findIndex(
      (n) => StyleSheet.flatten(n.props.style as ViewStyle)?.backgroundColor === colors.ink,
    );

const scrollTo = (r: renderer.ReactTestRenderer, x: number) =>
  r.root.findByType(FlatList).props.onScroll({ nativeEvent: { contentOffset: { x } } });

const settleAt = (r: renderer.ReactTestRenderer, x: number) =>
  r.root.findByType(FlatList).props.onMomentumScrollEnd({ nativeEvent: { contentOffset: { x } } });

async function scrollToPage(r: renderer.ReactTestRenderer, page: number) {
  const { offset } = r.root.findByType(FlatList).props.getItemLayout(null, page);
  await act(async () => scrollTo(r, offset));
}

let tree: renderer.ReactTestRenderer | null = null;

beforeEach(() => {
  (useSaveOptimistic as jest.Mock).mockReturnValue({ saved: false, toggle: jest.fn() });
  setMatches(undefined);
});
afterEach(() => {
  act(() => tree?.unmount());
  tree = null;
  jest.clearAllMocks();
});

async function mount() {
  await act(async () => {
    tree = renderer.create(<PostCarousel post={post} />);
  });
  return tree!;
}

describe("PostCarousel", () => {
  it("first slide shows overseas hook with country chip and info button", async () => {
    const r = await mount();
    expect(text(r)).toContain("도쿄 타워");
    expect(text(r)).toContain("일본");
    expect(text(r)).toContain("도쿄의 상징적인 전망 타워");
    expect(r.root.findAllByProps({ testID: "credit-info" }).length).toBeGreaterThan(0);
  });

  it("hides the counter and dots until the real match count is known", async () => {
    const r = await mount();
    expect(text(r)).not.toContain("1/4");
    expect(r.root.findAllByProps({ testID: "post-counter" })).toHaveLength(0);
  });

  it("shows the counter from the actual match count once loaded", async () => {
    setMatches([match({ contentId: "100" }), match({ contentId: "101" })]);
    const r = await mount();
    expect(text(r)).toContain("1/3");
    expect(text(r)).not.toContain("1/4");
  });

  it("matches query stays disabled until first swipe", async () => {
    await mount();
    expect(useMatches).toHaveBeenCalledWith(7, { enabled: false });
  });

  it("prefetches the first match image bytes once matches arrive (warms the original shown in the feed)", async () => {
    const prefetch = jest.spyOn(Image, "prefetch").mockResolvedValue(true);
    setMatches([
      match({ contentId: "100", imageUrl: "https://tong.visitkorea.or.kr/a_image1_1.jpg" }),
      match({ contentId: "101", imageUrl: "https://tong.visitkorea.or.kr/b_image1_1.jpg" }),
    ]);
    await mount();
    expect(prefetch).toHaveBeenCalledWith(
      "https://img.pictrip.org/tong.visitkorea.or.kr/a_image1_1.jpg",
      {
        cachePolicy: "memory-disk",
      },
    );
  });

  it("after swipe, match slides render number, name, region, overview", async () => {
    setMatches([
      match({ contentId: "100", title: "남산 서울타워" }),
      match({ contentId: "101", title: "부산타워" }),
      match({ contentId: "102", title: "여수 타워" }),
    ]);
    const r = await mount();
    expect(text(r)).toContain("남산 서울타워");
    expect(text(r)).toContain("서울 용산구");
    expect(text(r)).toContain("서울의 전망 명소");
    expect(r.root.findAllByProps({ testID: "match-number" }).length).toBeGreaterThan(0);
  });

  it("match slides render the KTO original with a mid-size blur-up preview", async () => {
    setMatches([match({ imageUrl: "https://tong.visitkorea.or.kr/a_image1_1.jpg" })]);
    const r = await mount();
    const ktoUris = r.root
      .findAllByType(Image)
      .map((n) => n.props.source?.uri)
      .filter((uri): uri is string => typeof uri === "string" && uri.includes("tong.visitkorea"));
    expect(ktoUris).toContain("https://img.pictrip.org/tong.visitkorea.or.kr/a_image1_1.jpg");
    expect(ktoUris).toContain("https://img.pictrip.org/tong.visitkorea.or.kr/a_image2_1.jpg");
  });

  it("match slide bookmark toggles via save hook", async () => {
    const toggle = jest.fn();
    (useSaveOptimistic as jest.Mock).mockReturnValue({ saved: false, toggle });
    setMatches([match()]);
    const r = await mount();
    await scrollToPage(r, 1);
    await act(async () => {
      r.root.findAllByProps({ testID: "match-save" })[0].props.onPress();
    });
    expect(toggle).toHaveBeenCalled();
  });

  it("counter stays mounted across slides and only its number changes", async () => {
    setMatches([match({ contentId: "100" }), match({ contentId: "101" })]);
    const r = await mount();
    expect(rendered(r, "post-counter")).toBe(1);
    expect(text(r)).toContain("1/3");

    await scrollToPage(r, 2);
    expect(rendered(r, "post-counter")).toBe(1);
    expect(text(r)).toContain("3/3");
    expect(text(r)).not.toContain("1/3");
  });

  it("counter follows the scroll offset before the swipe settles", async () => {
    setMatches([match({ contentId: "100" }), match({ contentId: "101" })]);
    const r = await mount();
    await act(async () => scrollTo(r, CARD_WIDTH * 0.6));
    expect(text(r)).toContain("2/3");
  });

  it("top-left control swaps info for bookmark as the active slide changes", async () => {
    setMatches([match({ contentId: "100" })]);
    const r = await mount();
    expect(r.root.findAllByProps({ testID: "credit-info" }).length).toBeGreaterThan(0);
    expect(r.root.findAllByProps({ testID: "match-save" })).toHaveLength(0);

    await scrollToPage(r, 1);
    expect(r.root.findAllByProps({ testID: "credit-info" })).toHaveLength(0);
    expect(r.root.findAllByProps({ testID: "match-save" }).length).toBeGreaterThan(0);
  });

  it("keeps the card scrollable while the overlay sits above it", async () => {
    setMatches([match({ contentId: "100" })]);
    const r = await mount();
    expect(r.root.findByType(FlatList).props.scrollEnabled).toBe(true);
    await scrollToPage(r, 1);
    expect(r.root.findByType(FlatList).props.scrollEnabled).toBe(true);
  });

  it("match card press pushes the spot detail route", async () => {
    setMatches([match({ contentId: "555" })]);
    const r = await mount();
    await act(async () => {
      r.root.findAllByProps({ testID: "match-card" })[0].props.onPress();
    });
    expect(router.push).toHaveBeenCalledWith("/spots/555");
  });

  it("match card press runs onNavigate before pushing the spot detail route", async () => {
    setMatches([match({ contentId: "555" })]);
    const order: string[] = [];
    const onNavigate = jest.fn(() => order.push("navigate"));
    (router.push as jest.Mock).mockImplementation(() => order.push("push"));
    await act(async () => {
      tree = renderer.create(<PostCarousel post={post} onNavigate={onNavigate} />);
    });
    await act(async () => {
      tree!.root.findAllByProps({ testID: "match-card" })[0].props.onPress();
    });
    expect(onNavigate).toHaveBeenCalled();
    expect(router.push).toHaveBeenCalledWith("/spots/555");
    expect(order).toEqual(["navigate", "push"]);
  });

  it("zero matches keeps the hero swipeable but drops dots and counter", async () => {
    setMatches([]);
    const r = await mount();
    expect(text(r)).toContain("도쿄 타워");
    expect(text(r)).not.toContain("1/2");
    expect(r.root.findAllByProps({ testID: "post-counter" })).toHaveLength(0);
    expect(r.root.findByType(FlatList).props.scrollEnabled).toBe(true);
  });

  it("zero matches answers the swipe with a not-found slide", async () => {
    setMatches([]);
    const r = await mount();
    expect(r.root.findAllByProps({ testID: "match-empty" }).length).toBeGreaterThan(0);
    expect(text(r)).toContain(MATCH_EMPTY_TEXT);
  });

  it("waiting and zero-match states hold the same slide count", async () => {
    setMatches(undefined);
    const waiting = (await mount()).root.findByType(FlatList).props.data.length;
    act(() => tree?.unmount());
    tree = null;
    setMatches([]);
    const zero = (await mount()).root.findByType(FlatList).props.data.length;
    expect(waiting).toBe(zero);
  });

  it("index stays valid when a zero-match answer lands while parked on slide 2", async () => {
    const scrollToIndex = jest
      .spyOn(FlatList.prototype, "scrollToIndex")
      .mockImplementation(() => {});
    const r = await mount();
    await act(async () => {
      r.root.findByType(FlatList).props.onScrollBeginDrag();
      settleAt(r, CARD_WIDTH);
    });
    setMatches([]);
    await act(async () => {
      r.update(<PostCarousel post={post} />);
    });
    const slides = r.root.findByType(FlatList).props.data;
    expect(slides).toHaveLength(2);
    expect(slides[1].kind).toBe("empty");
    expect(r.root.findAllByProps({ testID: "match-empty" }).length).toBeGreaterThan(0);
    expect(scrollToIndex).not.toHaveBeenCalled();
    scrollToIndex.mockRestore();
  });

  it("clamps back to the last slide when the list shrinks under the offset", async () => {
    const scrollToIndex = jest
      .spyOn(FlatList.prototype, "scrollToIndex")
      .mockImplementation(() => {});
    setMatches([match({ contentId: "100" }), match({ contentId: "101" })]);
    const r = await mount();
    await act(async () => settleAt(r, CARD_WIDTH * 2));
    setMatches([]);
    await act(async () => {
      r.update(<PostCarousel post={post} />);
    });
    expect(scrollToIndex).toHaveBeenCalledWith({ index: 1, animated: false });
    scrollToIndex.mockRestore();
  });

  it("dots follow a settled swipe", async () => {
    setMatches([match({ contentId: "100" }), match({ contentId: "101" })]);
    const r = await mount();
    expect(activeDot(r)).toBe(0);
    await act(async () => {
      r.root.findByType(FlatList).props.onScrollBeginDrag();
      settleAt(r, CARD_WIDTH * 2);
    });
    expect(activeDot(r)).toBe(2);
  });

  it("dots follow the drag past each slide midpoint before it settles", async () => {
    setMatches([match({ contentId: "100" }), match({ contentId: "101" })]);
    const r = await mount();
    await act(async () => {
      r.root.findByType(FlatList).props.onScrollBeginDrag();
      scrollTo(r, CARD_WIDTH * 0.4);
    });
    expect(activeDot(r)).toBe(0);
    await act(async () => scrollTo(r, CARD_WIDTH * 0.6));
    expect(activeDot(r)).toBe(1);
  });

  it("first drag arms the matches query", async () => {
    const r = await mount();
    expect(useMatches).toHaveBeenLastCalledWith(7, { enabled: false });
    await act(async () => {
      r.root.findByType(FlatList).props.onScrollBeginDrag();
    });
    expect(useMatches).toHaveBeenLastCalledWith(7, { enabled: true });
  });

  it("a flick that outruns the drag still arms the matches query", async () => {
    const r = await mount();
    await act(async () => settleAt(r, CARD_WIDTH));
    expect(useMatches).toHaveBeenLastCalledWith(7, { enabled: true });
  });

  it("a drag alone never arms the matches query", async () => {
    const r = await mount();
    await act(async () => scrollTo(r, CARD_WIDTH));
    expect(useMatches).toHaveBeenLastCalledWith(7, { enabled: false });
  });

  it("dots track the corrected slide after the list shrinks and grows back", async () => {
    const scrollToIndex = jest
      .spyOn(FlatList.prototype, "scrollToIndex")
      .mockImplementation(() => {});
    setMatches([
      match({ contentId: "100" }),
      match({ contentId: "101" }),
      match({ contentId: "102" }),
    ]);
    const r = await mount();
    await act(async () => {
      r.root.findByType(FlatList).props.onScrollBeginDrag();
      settleAt(r, CARD_WIDTH * 2);
    });
    expect(activeDot(r)).toBe(2);

    setMatches([]);
    await act(async () => {
      r.update(<PostCarousel post={post} />);
    });
    expect(scrollToIndex).toHaveBeenCalledWith({ index: 1, animated: false });
    await act(async () => scrollTo(r, CARD_WIDTH));

    setMatches([
      match({ contentId: "100" }),
      match({ contentId: "101" }),
      match({ contentId: "102" }),
    ]);
    await act(async () => {
      r.update(<PostCarousel post={post} />);
    });
    expect(activeDot(r)).toBe(1);
    scrollToIndex.mockRestore();
  });

  it("info button opens credit sheet with three rows", async () => {
    const r = await mount();
    await act(async () => {
      r.root.findByProps({ testID: "credit-info" }).props.onPress();
    });
    expect(text(r)).toContain("촬영");
    expect(text(r)).toContain("라이선스");
    expect(text(r)).toContain("제공");
    expect(text(r)).toContain("김작가");
  });
});
