import renderer, { act } from "react-test-renderer";
import { Text } from "react-native";
import { TravelSheet, sheetStyles } from "@/features/travel/components/TravelSheet";
import { colors, shadows } from "@/constants/theme";

jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 59, bottom: 34, left: 0, right: 0 }),
}));

const base = {
  snap: "mid" as const,
  keyboardPx: 0,
  dockPx: 92,
  onGrabberTap: jest.fn(),
  onCollapse: jest.fn(),
  onSnapChange: jest.fn(),
};

function mount(props: Partial<React.ComponentProps<typeof TravelSheet>> = {}) {
  let tree: renderer.ReactTestRenderer;
  act(() => {
    tree = renderer.create(
      <TravelSheet {...base} {...props}>
        <Text>대화</Text>
      </TravelSheet>,
    );
  });
  return tree!;
}

function byId(tree: renderer.ReactTestRenderer, id: string) {
  return tree.root.findAllByProps({ testID: id });
}

function flatten(style: unknown): Record<string, unknown> {
  return Object.assign({}, ...[style].flat(Infinity).filter(Boolean)) as Record<string, unknown>;
}

const START_Y = 400;

function touch(dy: number, at = 0) {
  return { nativeEvent: { pageY: START_Y + dy, timestamp: at } };
}

function drag(tree: renderer.ReactTestRenderer, steps: number[]) {
  const header = byId(tree, "travel-sheet-header")[0];
  act(() => {
    steps.forEach((dy, index) => {
      const event = touch(dy, index * 16);
      if (index === 0) header.props.onResponderGrant(event);
      else if (index < steps.length - 1) header.props.onResponderMove(event);
      else header.props.onResponderRelease(event);
    });
  });
}

describe("TravelSheet", () => {
  it("collapsed에서는 그래버가 없다", () => {
    const tree = mount({ snap: "collapsed" });

    expect(byId(tree, "travel-sheet-grabber")).toHaveLength(0);
  });

  it("mid에서는 그래버가 있고 탭하면 onGrabberTap", () => {
    const onGrabberTap = jest.fn();
    const tree = mount({ snap: "mid", onGrabberTap });
    const grabber = byId(tree, "travel-sheet-grabber")[0];

    act(() => grabber.props.onPress());

    expect(onGrabberTap).toHaveBeenCalled();
    expect(grabber.props.accessibilityRole).toBe("button");
    expect(grabber.props.accessibilityLabel).toBe("시트 크기 전환");
  });

  it("collapsed에서는 내리기 버튼도 없다", () => {
    const tree = mount({ snap: "collapsed" });

    expect(byId(tree, "travel-sheet-collapse")).toHaveLength(0);
  });

  it("mid에서 내리기 버튼을 탭하면 onCollapse", () => {
    const onCollapse = jest.fn();
    const tree = mount({ snap: "mid", onCollapse });
    const button = byId(tree, "travel-sheet-collapse")[0];

    act(() => button.props.onPress());

    expect(onCollapse).toHaveBeenCalled();
    expect(button.props.accessibilityLabel).toBe("시트 내리기");
  });

  it("루트는 travel-sheet testID와 시트 스타일을 가진다", () => {
    const tree = mount({ snap: "mid" });

    expect(byId(tree, "travel-sheet").length).toBeGreaterThan(0);
    expect(sheetStyles.root.position).toBe("absolute");
    expect(sheetStyles.root.left).toBe(0);
    expect(sheetStyles.root.right).toBe(0);
    expect(sheetStyles.root.backgroundColor).toBe(colors.inset);
    expect(sheetStyles.root.borderTopLeftRadius).toBe(22);
    expect(sheetStyles.root.borderTopRightRadius).toBe(22);
    expect(sheetStyles.root.borderTopWidth).toBe(1);
    expect(sheetStyles.root.borderTopColor).toBe(colors.glassBorder);
    expect(sheetStyles.root.shadowRadius).toBe(shadows.sheet.shadowRadius);
    expect(sheetStyles.pill.width).toBe(44);
    expect(sheetStyles.pill.height).toBe(5);
    expect(sheetStyles.pill.backgroundColor).toBe(colors.fillStrong);
  });

  it("children이 시트 안에 그대로 렌더된다", () => {
    const tree = mount({ snap: "full" });

    expect(tree.root.findAllByType(Text).some((n) => n.props.children === "대화")).toBe(true);
  });

  it("collapsed에서는 패널 크롬을 걷어 도크만 남긴다", () => {
    const tree = mount({ snap: "collapsed" });
    const root = byId(tree, "travel-sheet")[0];

    expect(flatten(root.props.style)).toMatchObject({
      backgroundColor: "transparent",
      borderTopWidth: 0,
      borderTopLeftRadius: 0,
      shadowOpacity: 0,
    });
  });

  it("mid에서는 패널 크롬을 그린다", () => {
    const tree = mount({ snap: "mid" });
    const root = byId(tree, "travel-sheet")[0];

    expect(flatten(root.props.style)).toMatchObject({
      backgroundColor: colors.inset,
      borderTopWidth: 1,
      borderTopLeftRadius: 22,
    });
  });

  it("collapsed에서도 헤더는 드래그 손잡이로 남는다", () => {
    const tree = mount({ snap: "collapsed" });
    const header = byId(tree, "travel-sheet-header")[0];

    expect(header.props.onStartShouldSetResponder).toBeDefined();
  });

  it("헤더를 탭만 하면 자식 버튼이 먼저 받는다", () => {
    const tree = mount({ snap: "mid" });
    const header = byId(tree, "travel-sheet-header")[0];

    expect(header.props.onStartShouldSetResponder()).toBe(false);
    expect(header.props.onMoveShouldSetResponder()).toBe(true);
  });

  it("위로 끌어올리면 다음 스냅으로 올라간다", () => {
    const onSnapChange = jest.fn();
    const tree = mount({ snap: "collapsed", onSnapChange });

    drag(tree, [0, -120, -300]);

    expect(onSnapChange).toHaveBeenCalledWith("mid");
  });

  it("아래로 끌어내리면 다음 스냅으로 내려간다", () => {
    const onSnapChange = jest.fn();
    const tree = mount({ snap: "full", onSnapChange });

    drag(tree, [0, 120, 300]);

    expect(onSnapChange).toHaveBeenCalledWith("mid");
  });

  it("살짝만 끌고 놓으면 원래 스냅에 되돌아간다", () => {
    const onSnapChange = jest.fn();
    const tree = mount({ snap: "mid", onSnapChange });

    drag(tree, [0, -6, -8]);

    expect(onSnapChange).not.toHaveBeenCalled();
  });

  it("드래그 중에는 collapsed에서도 패널을 그린다", () => {
    const tree = mount({ snap: "collapsed" });
    const header = byId(tree, "travel-sheet-header")[0];

    act(() => header.props.onResponderGrant(touch(0)));

    expect(flatten(byId(tree, "travel-sheet")[0].props.style).backgroundColor).toBe(colors.inset);
  });
});
