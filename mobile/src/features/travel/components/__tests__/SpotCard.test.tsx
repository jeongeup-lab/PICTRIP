import renderer, { act } from "react-test-renderer";
import { SpotCard, DETAIL_ACTION } from "@/features/travel/components/SpotCard";
import type { TravelSpot } from "@/features/travel/api";

jest.mock("expo-router", () => ({ router: { push: jest.fn(), back: jest.fn() } }));
jest.mock("@/features/saved/hooks/use-save-optimistic", () => ({
  useSaveOptimistic: jest.fn(),
}));
jest.mock("@/features/spots/queries", () => ({ prefetchSpot: jest.fn() }));

const { useSaveOptimistic } = jest.requireMock("@/features/saved/hooks/use-save-optimistic") as {
  useSaveOptimistic: jest.Mock;
};
const toggle = jest.fn();

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

function saveButton(tree: renderer.ReactTestRenderer) {
  return tree.root
    .findAllByProps({ testID: "travel-spot-save-126508" })
    .find((node) => typeof node.props.onPress === "function")!;
}

describe("SpotCard 접근성", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    toggle.mockResolvedValue(true);
    useSaveOptimistic.mockReturnValue({ saved: false, toggle });
  });

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

describe("SpotCard 저장", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useSaveOptimistic.mockReturnValue({ saved: false, toggle });
  });

  it.each([true, false])("notifies the committed saved state %s", async (result) => {
    toggle.mockResolvedValueOnce(result);
    const onSaveToggle = jest.fn();
    const tree = mount({ onSaveToggle });

    await act(async () => saveButton(tree).props.onPress());

    expect(onSaveToggle).toHaveBeenCalledWith(result);
  });

  it("하트가 카드 밖 형제라 스크린 리더가 이름과 상태를 읽는다", () => {
    useSaveOptimistic.mockReturnValue({ saved: true, toggle });
    const tree = mount({ onPress: () => undefined, onDetail: () => undefined });
    const save = saveButton(tree);

    expect(save.props.accessibilityRole).toBe("button");
    expect(save.props.accessibilityLabel).toBe("저장 해제");
    expect(save.props.accessibilityState).toEqual({ selected: true });
    expect(cardPressable(tree).findAllByProps({ testID: "travel-spot-save-126508" })).toHaveLength(
      0,
    );
  });

  it("does not report a save result when auth or mutation fails", async () => {
    toggle.mockResolvedValueOnce(null);
    const onSaveToggle = jest.fn();
    const tree = mount({ onSaveToggle });
    const save = tree.root
      .findAllByProps({ testID: "travel-spot-save-126508" })
      .find((node) => typeof node.props.onPress === "function")!;

    await act(async () => save.props.onPress({ stopPropagation: jest.fn() }));

    expect(onSaveToggle).not.toHaveBeenCalled();
  });
});
