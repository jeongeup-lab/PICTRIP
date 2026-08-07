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

  afterEach(() => {
    act(() => tree?.unmount());
    tree = null;
  });

  function mount() {
    act(() => {
      tree = renderer.create(<AccessNotice />);
    });
    return lines(tree!);
  }

  it("separates required from optional access permissions", () => {
    const text = mount();

    expect(text).toContain("필수 접근권한");
    expect(text).toContain("선택 접근권한");
    expect(text.join("\n")).toContain("카메라");
    expect(text.join("\n")).toContain("사진");
    expect(text.join("\n")).toContain("위치");
  });

  it("gives every optional permission a reason and a fallback", () => {
    const text = mount().join("\n");

    expect(text).toContain("풍경을 찍어");
    expect(text).toContain("보관함에서 직접 고른");
    expect(text).toContain("내 주변 여행지");
    expect(text).toContain("거부해도 저장된 사진");
    expect(text).toContain("거부하면 서울 도심");
  });

  it("does not announce permissions the app never requests", () => {
    const text = mount().join("\n");

    expect(text.length).toBeGreaterThan(0);
    expect(text).not.toContain("마이크");
    expect(text).not.toContain("연락처");
    expect(text).not.toContain("알림");
  });
});
