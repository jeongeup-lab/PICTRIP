import renderer, { act } from "react-test-renderer";
import { ScrollView } from "react-native";
import { HeroCarousel } from "@/features/feed/components/HeroCarousel";
import type { HeroTile } from "@/lib/api-types";

jest.mock("expo-router", () => ({ router: { push: jest.fn() } }));

const heroes: HeroTile[] = [
  { id: 1, slug: "a", title: "가을 산책", subtitle: "사진이 예쁜 곳", coverUrl: null },
  { id: 2, slug: "b", title: "바다 풍경", subtitle: null, coverUrl: null },
  { id: 3, slug: "c", title: "골목 카페", subtitle: null, coverUrl: null },
];

describe("HeroCarousel counter", () => {
  let tree: renderer.ReactTestRenderer | null = null;

  afterEach(() => {
    act(() => tree?.unmount());
    tree = null;
    jest.clearAllMocks();
  });

  const counterText = () =>
    tree!.root.findAllByProps({ testID: "hero-counter" })[0].props.children as string;

  it("starts at 1 / N", async () => {
    await act(async () => {
      tree = renderer.create(<HeroCarousel heroes={heroes} />);
    });
    expect(counterText()).toBe("1 / 3");
  });

  it("advances the counter with the scroll index", async () => {
    await act(async () => {
      tree = renderer.create(<HeroCarousel heroes={heroes} />);
    });
    const sv = tree!.root.findByType(ScrollView);
    const interval = sv.props.snapToInterval as number;

    await act(async () => {
      sv.props.onMomentumScrollEnd({ nativeEvent: { contentOffset: { x: interval } } });
    });
    expect(counterText()).toBe("2 / 3");

    await act(async () => {
      sv.props.onMomentumScrollEnd({ nativeEvent: { contentOffset: { x: interval * 2 } } });
    });
    expect(counterText()).toBe("3 / 3");
  });

  it("clamps the counter to the last hero on overscroll", async () => {
    await act(async () => {
      tree = renderer.create(<HeroCarousel heroes={heroes} />);
    });
    const sv = tree!.root.findByType(ScrollView);
    const interval = sv.props.snapToInterval as number;

    await act(async () => {
      sv.props.onMomentumScrollEnd({ nativeEvent: { contentOffset: { x: interval * 9 } } });
    });
    expect(counterText()).toBe("3 / 3");
  });
});
