import renderer, { act } from "react-test-renderer";
import { Text } from "react-native";
import { IntroSection } from "@/features/spots/components/IntroSection";

const overview = "통영 중앙로의 벽화마을은 언덕을 따라 이어진 골목마다 그림이 있다.";

function mount(text: string | null = overview) {
  let tree: renderer.ReactTestRenderer;
  act(() => {
    tree = renderer.create(<IntroSection overview={text} />);
  });
  return tree!;
}

function measureNode(tree: renderer.ReactTestRenderer) {
  return tree.root
    .findAllByProps({ testID: "intro-measure" })
    .find((node) => typeof node.props.onTextLayout === "function");
}

function reportLines(tree: renderer.ReactTestRenderer, count: number) {
  const node = measureNode(tree);
  act(() => {
    node?.props.onTextLayout({
      nativeEvent: { lines: Array.from({ length: count }, () => ({})) },
    });
  });
}

function toggle(tree: renderer.ReactTestRenderer) {
  return tree.root.findAll((node) => typeof node.props.onPress === "function")[0];
}

function toggleLabel(tree: renderer.ReactTestRenderer) {
  return tree.root
    .findAllByType(Text)
    .map((node) => node.props.children)
    .filter((child) => child === "더보기" || child === "접기");
}

function visibleOverview(tree: renderer.ReactTestRenderer) {
  return tree.root
    .findAllByType(Text)
    .find((node) => node.props.children === overview && node.props.testID !== "intro-measure");
}

describe("IntroSection", () => {
  it("소개글이 없으면 아무것도 그리지 않는다", () => {
    expect(mount(null).toJSON()).toBeNull();
    expect(mount("").toJSON()).toBeNull();
    expect(mount("<p></p>").toJSON()).toBeNull();
  });

  it("재기 전에는 토글을 그리지 않는다", () => {
    expect(toggleLabel(mount())).toEqual([]);
  });

  it("다섯 줄에 들어가면 토글이 없다", () => {
    const tree = mount();

    reportLines(tree, 5);

    expect(toggleLabel(tree)).toEqual([]);
  });

  it("다섯 줄을 넘기면 더보기가 붙고 눌러 펼쳤다 접는다", () => {
    const tree = mount();

    reportLines(tree, 6);
    expect(toggleLabel(tree)).toEqual(["더보기"]);
    expect(visibleOverview(tree)?.props.numberOfLines).toBe(5);

    act(() => {
      toggle(tree).props.onPress();
    });

    expect(toggleLabel(tree)).toEqual(["접기"]);
    expect(visibleOverview(tree)?.props.numberOfLines).toBeUndefined();

    act(() => {
      toggle(tree).props.onPress();
    });

    expect(toggleLabel(tree)).toEqual(["더보기"]);
    expect(visibleOverview(tree)?.props.numberOfLines).toBe(5);
  });

  it("다른 소개글로 바뀌면 새로 잴 때까지 토글을 감춘다", () => {
    const tree = mount();

    reportLines(tree, 6);
    expect(toggleLabel(tree)).toEqual(["더보기"]);

    act(() => {
      tree.update(<IntroSection overview="한산도 앞바다가 보이는 언덕길." />);
    });
    expect(toggleLabel(tree)).toEqual([]);

    reportLines(tree, 7);
    expect(toggleLabel(tree)).toEqual(["더보기"]);
  });

  it("줄 수가 다시 줄면 토글을 거둔다", () => {
    const tree = mount();

    reportLines(tree, 6);
    reportLines(tree, 4);

    expect(toggleLabel(tree)).toEqual([]);
  });

  it("재기용 사본은 클램프를 두 배로 늘리지 않는다", () => {
    const tree = mount();

    expect(measureNode(tree)?.props.numberOfLines).toBe(6);
  });

  it("재기용 사본은 접근성 트리와 터치에서 빠진다", () => {
    const tree = mount();
    const layer = tree.root
      .findAll((node) => node.props.accessibilityElementsHidden === true)
      .find((node) => node.props.importantForAccessibility === "no-hide-descendants");

    expect(layer?.props.pointerEvents).toBe("none");
    expect(layer?.findAllByProps({ testID: "intro-measure" }).length).toBeGreaterThan(0);
  });
});
