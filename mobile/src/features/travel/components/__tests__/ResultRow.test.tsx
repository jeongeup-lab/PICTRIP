import renderer, { act } from "react-test-renderer";
import { Text } from "react-native";
import { ResultRow, DETAIL_ACTION } from "@/features/travel/components/ResultRow";
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

function mount(props: Partial<React.ComponentProps<typeof ResultRow>> = {}) {
  let tree: renderer.ReactTestRenderer;
  act(() => {
    tree = renderer.create(<ResultRow spot={spot} index={0} {...props} />);
  });
  return tree!;
}

function rowPressable(tree: renderer.ReactTestRenderer) {
  return tree.root.findAllByProps({ testID: "travel-spot-126508" })[0];
}

function saveButton(tree: renderer.ReactTestRenderer) {
  return tree.root
    .findAllByProps({ testID: "travel-spot-save-126508" })
    .find((node) => typeof node.props.onPress === "function")!;
}

const flatten = (node: unknown): string =>
  Array.isArray(node)
    ? node.map(flatten).join("")
    : typeof node === "string" || typeof node === "number"
      ? String(node)
      : "";

const texts = (tree: renderer.ReactTestRenderer): string =>
  tree.root
    .findAllByType(Text)
    .map((n) => flatten(n.props.children))
    .join("");

beforeEach(() => {
  jest.clearAllMocks();
  toggle.mockResolvedValue(true);
  useSaveOptimistic.mockReturnValue({ saved: false, toggle });
});

describe("ResultRow 표시", () => {
  it("지도 핀과 같은 번호를 앞에 단다", () => {
    expect(texts(mount({ index: 2 }))).toContain("3");
  });

  it("거리를 아는 결과만 거리를 붙인다", () => {
    expect(texts(mount({ distanceKm: 12.4 }))).toContain("12");
    expect(texts(mount({ distanceKm: null }))).not.toContain("km");
  });
});

describe("ResultRow 접근성", () => {
  it("스크린 리더에 상세 보기 액션을 준다 — 두 번 탭이 한 번으로 합쳐지기 때문", () => {
    const onDetail = jest.fn();
    const tree = mount({ onPress: () => undefined, onDetail });
    const pressable = rowPressable(tree);

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
      rowPressable(tree).props.onAccessibilityAction({ nativeEvent: { actionName: "activate" } }),
    );

    expect(onDetail).not.toHaveBeenCalled();
  });

  it("탭 두 뜻이 없는 행에는 액션을 붙이지 않는다", () => {
    const pressable = rowPressable(mount());

    expect(pressable.props.accessibilityActions).toBeUndefined();
    expect(pressable.props.accessibilityHint).toBeUndefined();
  });
});

describe("ResultRow 저장", () => {
  it.each([true, false])("notifies the committed saved state %s", async (result) => {
    toggle.mockResolvedValueOnce(result);
    const onSaveToggle = jest.fn();
    const tree = mount({ onSaveToggle });

    await act(async () => saveButton(tree).props.onPress());

    expect(onSaveToggle).toHaveBeenCalledWith(result);
  });

  it("하트가 행 밖 형제라 스크린 리더가 이름과 상태를 읽는다", () => {
    useSaveOptimistic.mockReturnValue({ saved: true, toggle });
    const tree = mount({ onPress: () => undefined, onDetail: () => undefined });
    const save = saveButton(tree);

    expect(save.props.accessibilityRole).toBe("button");
    expect(save.props.accessibilityLabel).toBe("저장 해제");
    expect(save.props.accessibilityState).toEqual({ selected: true });
    expect(rowPressable(tree).findAllByProps({ testID: "travel-spot-save-126508" })).toHaveLength(
      0,
    );
  });

  it("does not report a save result when auth or mutation fails", async () => {
    toggle.mockResolvedValueOnce(null);
    const onSaveToggle = jest.fn();
    const tree = mount({ onSaveToggle });

    await act(async () => saveButton(tree).props.onPress({ stopPropagation: jest.fn() }));

    expect(onSaveToggle).not.toHaveBeenCalled();
  });
});
