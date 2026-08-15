import renderer, { act } from "react-test-renderer";
import { Text } from "react-native";
import { VisitSection } from "@/features/spots/components/VisitSection";

const render = async (props: Partial<Parameters<typeof VisitSection>[0]> = {}) => {
  let tree: renderer.ReactTestRenderer | null = null;
  await act(async () => {
    tree = renderer.create(
      <VisitSection
        title="무릉계곡"
        saved={false}
        onShare={jest.fn()}
        onScrap={jest.fn()}
        {...props}
      />,
    );
  });
  if (tree === null) throw new Error("section did not mount");
  return tree as renderer.ReactTestRenderer;
};

const textOf = (tree: renderer.ReactTestRenderer) =>
  tree.root
    .findAllByType(Text)
    .map((node) => JSON.stringify(node.props.children))
    .join("|");

describe("VisitSection 스크랩 버튼", () => {
  it("저장 전에는 빈 북마크와 '스크랩'을 보여준다", async () => {
    const tree = await render({ saved: false });

    expect(tree.root.findAllByProps({ name: "bookmark" }).length).toBeGreaterThan(0);
    expect(tree.root.findAllByProps({ name: "bookmark-fill" })).toHaveLength(0);
    expect(textOf(tree)).toContain("스크랩");
  });

  it("저장한 뒤에는 채운 북마크로 바뀌어 눌린 것이 보인다", async () => {
    const tree = await render({ saved: true });

    expect(tree.root.findAllByProps({ name: "bookmark-fill" }).length).toBeGreaterThan(0);
    expect(tree.root.findAllByProps({ name: "bookmark" })).toHaveLength(0);
    expect(textOf(tree)).toContain("스크랩됨");
  });

  it("스크랩 상태를 접근성에도 노출한다", async () => {
    const tree = await render({ saved: true });

    expect(tree.root.findByProps({ testID: "visit-scrap" }).props.accessibilityState).toEqual({
      selected: true,
    });
  });

  it("스크랩과 공유를 각각의 핸들러로 보낸다", async () => {
    const onScrap = jest.fn();
    const onShare = jest.fn();
    const tree = await render({ onScrap, onShare });

    await act(async () => tree.root.findByProps({ testID: "visit-scrap" }).props.onPress());
    expect(onScrap).toHaveBeenCalledTimes(1);
    expect(onShare).not.toHaveBeenCalled();

    await act(async () => tree.root.findByProps({ testID: "visit-share" }).props.onPress());
    expect(onShare).toHaveBeenCalledTimes(1);
  });
});
