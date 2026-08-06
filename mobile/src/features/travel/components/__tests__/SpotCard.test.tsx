import renderer, { act } from "react-test-renderer";
import { SpotCard, DETAIL_ACTION } from "@/features/travel/components/SpotCard";
import type { TravelSpot } from "@/features/travel/api";

jest.mock("expo-router", () => ({ router: { push: jest.fn(), back: jest.fn() } }));
jest.mock("@/features/saved/hooks/use-save-optimistic", () => ({
  useSaveOptimistic: () => ({ saved: false, toggle: jest.fn() }),
}));
jest.mock("@/features/spots/queries", () => ({ prefetchSpot: jest.fn() }));

const spot: TravelSpot = {
  contentId: "126508",
  title: "무릉계곡",
  regionLabel: "강원도 동해시",
  imageUrl: null,
  tag: "하위 8%",
  lat: null,
  lng: null,
};

function mount(props: Partial<React.ComponentProps<typeof SpotCard>> = {}) {
  let tree: renderer.ReactTestRenderer;
  act(() => {
    tree = renderer.create(<SpotCard spot={spot} {...props} />);
  });
  return tree!;
}

function cardPressable(tree: renderer.ReactTestRenderer) {
  return tree.root.findAllByProps({ testID: "travel-spot-126508" })[0];
}

describe("SpotCard 접근성", () => {
  it("스크린 리더에 상세 보기 액션을 준다 — 두 번 탭이 한 번으로 합쳐지기 때문", () => {
    const onDetail = jest.fn();
    const tree = mount({ onPress: () => undefined, onDetail });
    const pressable = cardPressable(tree);

    expect(pressable.props.accessibilityActions).toEqual([
      { name: DETAIL_ACTION, label: "상세 보기" },
    ]);

    act(() =>
      pressable.props.onAccessibilityAction({ nativeEvent: { actionName: DETAIL_ACTION } }),
    );

    expect(onDetail).toHaveBeenCalledTimes(1);
  });

  it("다른 액션 이름에는 반응하지 않는다", () => {
    const onDetail = jest.fn();
    const tree = mount({ onPress: () => undefined, onDetail });

    act(() =>
      cardPressable(tree).props.onAccessibilityAction({ nativeEvent: { actionName: "activate" } }),
    );

    expect(onDetail).not.toHaveBeenCalled();
  });

  it("탭 두 뜻이 없는 카드에는 액션을 붙이지 않는다", () => {
    const pressable = cardPressable(mount());

    expect(pressable.props.accessibilityActions).toBeUndefined();
    expect(pressable.props.accessibilityHint).toBeUndefined();
  });
});
