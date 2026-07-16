import renderer, { act } from "react-test-renderer";
import { FlatList } from "react-native";
import { Image } from "expo-image";
import { router } from "expo-router";
import { PostCarousel } from "@/features/feed/components/PostCarousel";
import { useMatches } from "@/features/feed/posts-queries";
import { useSaveOptimistic } from "@/features/saved/hooks/use-save-optimistic";
import type { MatchCard, OverseasPost } from "@/features/feed/posts-api";

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
    expect(text(r)).toContain("1/4");
  });

  it("matches query stays disabled until first swipe", async () => {
    await mount();
    expect(useMatches).toHaveBeenCalledWith(7, { enabled: false });
  });

  it("prefetches the first match image bytes once matches arrive (warms the ~940px mid-size shown in the feed)", async () => {
    const prefetch = jest.spyOn(Image, "prefetch").mockResolvedValue(true);
    setMatches([
      match({ contentId: "100", imageUrl: "https://tong.visitkorea.or.kr/a_image1_1.jpg" }),
      match({ contentId: "101", imageUrl: "https://tong.visitkorea.or.kr/b_image1_1.jpg" }),
    ]);
    await mount();
    expect(prefetch).toHaveBeenCalledWith(
      "https://img.pictrip.org/tong.visitkorea.or.kr/a_image2_1.jpg",
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

  it("match slides render the KTO mid-size cover-fill (single image, no blur-up preview)", async () => {
    setMatches([match({ imageUrl: "https://tong.visitkorea.or.kr/a_image1_1.jpg" })]);
    const r = await mount();
    const ktoImages = r.root
      .findAllByType(Image)
      .filter(
        (n) =>
          typeof n.props.source?.uri === "string" &&
          n.props.source.uri.includes("tong.visitkorea.or.kr"),
      );
    expect(ktoImages.length).toBe(1);
    expect(ktoImages[0].props.source.uri).toBe(
      "https://img.pictrip.org/tong.visitkorea.or.kr/a_image2_1.jpg",
    );
  });

  it("match slide bookmark toggles via save hook", async () => {
    const toggle = jest.fn();
    (useSaveOptimistic as jest.Mock).mockReturnValue({ saved: false, toggle });
    setMatches([match()]);
    const r = await mount();
    const stopPropagation = jest.fn();
    await act(async () => {
      r.root.findAllByProps({ testID: "match-save" })[0].props.onPress({ stopPropagation });
    });
    expect(stopPropagation).toHaveBeenCalled();
    expect(toggle).toHaveBeenCalled();
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

  it("zero matches renders only the hero with swipe, dots and counter removed", async () => {
    setMatches([]);
    const r = await mount();
    expect(text(r)).toContain("도쿄 타워");
    expect(text(r)).not.toContain("1/1");
    expect(r.root.findAllByProps({ testID: "post-counter" })).toHaveLength(0);
    expect(r.root.findByType(FlatList).props.scrollEnabled).toBe(false);
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
