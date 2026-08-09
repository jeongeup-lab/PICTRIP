import renderer, { act } from "react-test-renderer";
import { Text } from "react-native";
import {
  EmptyGreeting,
  GREETING_LINE1,
  GREETING_LINE2,
  ACCENT_SPAN,
  SAMPLES_CAPTION,
  SAMPLE_MOODS,
} from "@/features/travel/components/EmptyGreeting";

const base = {
  onSample: jest.fn(),
  onAlbum: jest.fn(),
  onShoot: jest.fn(),
};

function mount(props: Partial<React.ComponentProps<typeof EmptyGreeting>> = {}) {
  let tree: renderer.ReactTestRenderer;
  act(() => {
    tree = renderer.create(<EmptyGreeting {...base} {...props} />);
  });
  return tree!;
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

function byId(tree: renderer.ReactTestRenderer, id: string) {
  return tree.root
    .findAllByProps({ testID: id })
    .filter((n) => typeof n.props.onPress === "function");
}

beforeEach(() => jest.clearAllMocks());

describe("EmptyGreeting", () => {
  it("인사 카피와 캡션을 렌더한다", () => {
    const tree = mount();
    expect(texts(tree)).toContain(GREETING_LINE1);
    expect(texts(tree)).toContain(SAMPLES_CAPTION);
  });

  it("두 번째 줄은 조각을 합치면 원문 그대로다", () => {
    const tree = mount();
    expect(GREETING_LINE2).toContain(ACCENT_SPAN);
    expect(texts(tree)).toContain(ACCENT_SPAN);
  });

  it("예시 타일 탭은 해당 질문으로 onSample", () => {
    const tree = mount();
    act(() => byId(tree, "travel-sample-0")[0].props.onPress());
    expect(base.onSample).toHaveBeenCalledWith("바다 노을이 예쁜 여행지 알려줘");
  });

  it("예시 타일은 무드 목록과 같은 수로 라벨을 그린다", () => {
    const tree = mount();
    for (const [index, mood] of SAMPLE_MOODS.entries()) {
      expect(byId(tree, `travel-sample-${index}`)).toHaveLength(1);
      expect(texts(tree)).toContain(mood.label);
    }
  });

  it("앨범/촬영 CTA", () => {
    const tree = mount();
    act(() => byId(tree, "travel-empty-album")[0].props.onPress());
    act(() => byId(tree, "travel-empty-shoot")[0].props.onPress());
    expect(base.onAlbum).toHaveBeenCalled();
    expect(base.onShoot).toHaveBeenCalled();
  });
});
