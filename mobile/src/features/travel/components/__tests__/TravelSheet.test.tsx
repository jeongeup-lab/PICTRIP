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
});
