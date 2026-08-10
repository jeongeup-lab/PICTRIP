import { Text } from "react-native";
import renderer, { act } from "react-test-renderer";
import { AccessNotice, DENIED_TOGGLE_LABEL } from "@/features/consent/components/AccessNotice";

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

  function toggleDenied() {
    act(() =>
      tree!.root
        .findAll((node) => node.props?.testID === "access-denied-toggle")[0]
        .props.onPress(),
    );
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

  it("states the purpose of every optional permission up front", () => {
    const text = mount().join("\n");

    expect(text).toContain("고른 사진 한 장으로 닮은 여행지를 찾을 때만");
    expect(text).toContain("내 주변 여행지");
  });

  it("keeps the denial detail folded away until asked", () => {
    const collapsed = mount().join("\n");

    expect(collapsed).toContain(DENIED_TOGGLE_LABEL);
    expect(collapsed).not.toContain("보관함 전체를 읽지 않아요");
    expect(collapsed).not.toContain("서울 도심");

    const expanded = toggleDenied().join("\n");

    expect(expanded).toContain("보관함 전체를 읽지 않아요");
    expect(expanded).toContain("서울 도심");
  });

  it("does not announce permissions the app never requests", () => {
    const text = mount().join("\n");

    expect(text.length).toBeGreaterThan(0);
    expect(text).not.toContain("마이크");
    expect(text).not.toContain("연락처");
    expect(text).not.toContain("알림");
  });
});
