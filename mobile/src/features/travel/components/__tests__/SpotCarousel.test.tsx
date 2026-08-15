import renderer, { act } from "react-test-renderer";
import { FlatList, StyleSheet, View } from "react-native";
import { Skeleton } from "@/components/Skeleton";
import {
  SpotCarousel,
  SpotCarouselSkeleton,
  carouselIndexAt,
  progressRatio,
  CAROUSEL_BLOCK_PX,
} from "@/features/travel/components/SpotCarousel";
import { CARD_HEIGHT, CARD_STRIDE, CARD_WIDTH } from "@/features/travel/components/SpotCard";
import type { TravelSpot } from "@/features/travel/api";

jest.mock("@/features/saved/hooks/use-save-optimistic", () => ({
  useSaveOptimistic: () => ({ saved: false, toggle: jest.fn() }),
}));
jest.mock("@/features/spots/queries", () => ({ prefetchSpot: jest.fn() }));

const spots: TravelSpot[] = [1, 2, 3].map((n) => ({
  contentId: String(n),
  title: `장소 ${n}`,
  regionLabel: "제주시",
  imageUrl: null,
  tag: "한산",
  lat: 33 + n / 100,
  lng: 126,
}));

const base = {
  spots,
  tagBasis: null,
  focusedIndex: 0,
  origin: null,
  onFocusChange: jest.fn(),
  onDetail: jest.fn(),
  onSaveToggle: jest.fn(),
  onMetricPress: jest.fn(),
};

const mounted: renderer.ReactTestRenderer[] = [];

function mount(props: Partial<React.ComponentProps<typeof SpotCarousel>> = {}) {
  let tree: renderer.ReactTestRenderer;
  act(() => {
    tree = renderer.create(<SpotCarousel {...base} {...props} />);
  });
  mounted.push(tree!);
  return tree!;
}

function settleAt(list: renderer.ReactTestInstance, index: number) {
  list.props.onMomentumScrollEnd({ nativeEvent: { contentOffset: { x: CARD_STRIDE * index } } });
}

afterEach(() => {
  act(() => {
    for (const tree of mounted.splice(0)) tree.unmount();
  });
  jest.restoreAllMocks();
});

describe("carouselIndexAt", () => {
  it("반 칸을 넘기면 다음 카드로 센다", () => {
    expect(carouselIndexAt(0, 3)).toBe(0);
    expect(carouselIndexAt(CARD_STRIDE * 0.6, 3)).toBe(1);
    expect(carouselIndexAt(CARD_STRIDE * 2, 3)).toBe(2);
  });

  it("목록 밖으로 나가지 않는다", () => {
    expect(carouselIndexAt(-40, 3)).toBe(0);
    expect(carouselIndexAt(CARD_STRIDE * 9, 3)).toBe(2);
    expect(carouselIndexAt(0, 0)).toBe(0);
  });
});

describe("progressRatio", () => {
  it("보고 있는 위치를 퍼센트로 준다", () => {
    expect(progressRatio(0, 8)).toBeCloseTo(12.5);
    expect(progressRatio(7, 8)).toBe(100);
  });

  it("결과가 없으면 0이다", () => {
    expect(progressRatio(0, 0)).toBe(0);
  });
});

describe("SpotCarousel", () => {
  it("카드마다 스냅 오프셋을 준다", () => {
    const list = mount().root.findByType(FlatList);

    expect(list.props.snapToOffsets).toEqual([0, CARD_STRIDE, CARD_STRIDE * 2]);
  });

  it("멈춘 자리를 인덱스로 알린다", () => {
    const onFocusChange = jest.fn();
    const list = mount({ onFocusChange }).root.findByType(FlatList);

    act(() =>
      list.props.onMomentumScrollEnd({ nativeEvent: { contentOffset: { x: CARD_STRIDE } } }),
    );

    expect(onFocusChange).toHaveBeenCalledWith(1);
  });

  it("같은 인덱스로는 다시 알리지 않는다", () => {
    const onFocusChange = jest.fn();
    const list = mount({ onFocusChange }).root.findByType(FlatList);

    act(() => list.props.onMomentumScrollEnd({ nativeEvent: { contentOffset: { x: 4 } } }));

    expect(onFocusChange).not.toHaveBeenCalled();

    act(() => settleAt(list, 1));
    act(() => settleAt(list, 1));

    expect(onFocusChange).toHaveBeenCalledTimes(1);
  });

  it("핀 탭 인덱스로 스크롤한다", () => {
    const scrollToOffset = jest.spyOn(FlatList.prototype, "scrollToOffset");

    mount({ scrollToIndex: 2 });

    expect(scrollToOffset).toHaveBeenCalledWith({ offset: CARD_STRIDE * 2, animated: true });
  });

  it("핀 탭으로 옮긴 자리는 되알리지 않는다", () => {
    jest.spyOn(FlatList.prototype, "scrollToOffset").mockImplementation(() => {});
    const onFocusChange = jest.fn();
    const list = mount({ onFocusChange, scrollToIndex: 2 }).root.findByType(FlatList);

    act(() => settleAt(list, 2));

    expect(onFocusChange).not.toHaveBeenCalled();
  });

  it("새 답변에서는 같은 자리라도 다시 알린다", () => {
    const onFocusChange = jest.fn();
    const tree = mount({ onFocusChange });
    const list = tree.root.findByType(FlatList);

    act(() => settleAt(list, 2));
    expect(onFocusChange).toHaveBeenCalledWith(2);

    act(() => {
      tree.update(
        <SpotCarousel
          {...base}
          spots={spots.map((spot) => ({ ...spot }))}
          focusedIndex={0}
          onFocusChange={onFocusChange}
        />,
      );
    });
    act(() => settleAt(tree.root.findByType(FlatList), 2));

    expect(onFocusChange).toHaveBeenCalledTimes(2);
    expect(onFocusChange).toHaveBeenLastCalledWith(2);
  });

  it("결과가 있으면 진행 바를 그린다", () => {
    expect(mount().root.findAllByProps({ testID: "travel-progress-fill" }).length).toBeGreaterThan(
      0,
    );
  });

  it("결과가 없으면 아무것도 그리지 않는다", () => {
    expect(mount({ spots: [] }).root.findAllByType(FlatList)).toHaveLength(0);
  });
});

describe("SpotCarouselSkeleton", () => {
  function mountSkeleton() {
    let tree: renderer.ReactTestRenderer;
    act(() => {
      tree = renderer.create(<SpotCarouselSkeleton />);
    });
    mounted.push(tree!);
    return tree!;
  }

  it("카드 자리를 회색 판으로 채운다", () => {
    const cards = mountSkeleton().root.findAllByType(Skeleton);

    expect(cards.length).toBeGreaterThan(1);
    for (const card of cards) {
      expect(card.props.width).toBe(CARD_WIDTH);
      expect(card.props.height).toBe(CARD_HEIGHT);
    }
  });

  it("제스처를 먹지 않고 지도로 흘려보낸다", () => {
    const root = mountSkeleton().root.findByProps({ testID: "travel-carousel-skeleton" });

    expect(root.props.pointerEvents).toBe("none");
  });

  it("목록도 진행 바 채움도 만들지 않는다", () => {
    const tree = mountSkeleton();

    expect(tree.root.findAllByType(FlatList)).toHaveLength(0);
    expect(tree.root.findAllByProps({ testID: "travel-progress-fill" })).toHaveLength(0);
  });

  it("결과가 왔을 때와 같은 높이를 차지한다", () => {
    const tree = mountSkeleton();
    const track = tree.root.findAllByType(View).find((node) => {
      const style = StyleSheet.flatten(node.props.style);
      return typeof style?.marginTop === "number" && typeof style?.marginBottom === "number";
    });
    const style = StyleSheet.flatten(track?.props.style);

    expect(CARD_HEIGHT + style.marginTop + style.height + style.marginBottom).toBe(
      CAROUSEL_BLOCK_PX,
    );
  });
});
