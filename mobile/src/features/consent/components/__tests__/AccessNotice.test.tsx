import { Text } from "react-native";
import renderer, { act } from "react-test-renderer";
import { AccessNotice } from "@/features/consent/components/AccessNotice";

const flatten = (node: unknown): string =>
  Array.isArray(node)
    ? node.map(flatten).join("")
    : typeof node === "string" || typeof node === "number"
      ? String(node)
      : "";

function lines(tree: renderer.ReactTestRenderer): string[] {
  return tree.root.findAllByType(Text).map((n) => flatten(n.props.children));
}

describe("AccessNotice", () => {
  let tree: renderer.ReactTestRenderer | null = null;
  let onConfirm: jest.Mock;

  afterEach(() => {
    act(() => tree?.unmount());
    tree = null;
  });

  function mount() {
    onConfirm = jest.fn();
    act(() => {
      tree = renderer.create(<AccessNotice onConfirm={onConfirm} />);
    });
    return lines(tree!);
  }

  it("separates required from optional access permissions", () => {
    const text = mount();

    expect(text).toContain("필수적 접근 권한");
    expect(text).toContain("필수적 접근 권한 없음");
    expect(text).toContain("선택적 접근 권한");
    expect(text.join("\n")).toContain("사진 · 카메라");
    expect(text.join("\n")).toContain("위치 정보");
  });

  it("states the purpose of every optional permission up front", () => {
    const text = mount().join("\n");

    expect(text).toContain("사진 한 장으로 닮은 여행지 검색");
    expect(text).toContain("내 주변 인기 여행지 추천");
  });

  it("explains that optional permissions are asked lazily and reversible", () => {
    const text = mount().join("\n");

    expect(text).toContain("처음 쓸 때 물어보며");
    expect(text).toContain("언제든 바꿀 수 있어요");
  });

  it("confirms through the in-card button", () => {
    mount();
    act(() => {
      tree!.root.findAll((n) => n.props?.testID === "access-confirm")[0].props.onPress();
    });
    expect(onConfirm).toHaveBeenCalled();
  });

  it("does not announce permissions the app never requests", () => {
    const text = mount().join("\n");

    expect(text.length).toBeGreaterThan(0);
    expect(text).not.toContain("마이크");
    expect(text).not.toContain("연락처");
    expect(text).not.toContain("알림");
  });
});
