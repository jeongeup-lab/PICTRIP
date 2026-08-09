import renderer, { act } from "react-test-renderer";
import { Text, TextInput } from "react-native";
import { TravelDock, dockStyles } from "@/features/travel/components/TravelDock";
import {
  DOCK_ATTACH_ROW_PX,
  DOCK_FIELD_PX,
  DOCK_PAD_BOTTOM_PX,
  DOCK_PRIMER_PX,
} from "@/features/travel/lib/screen-layout";

const photo = { uri: "file://a.jpg", name: "a.jpg", type: "image/jpeg" };

const base = {
  value: "",
  photo: null,
  disabled: false,
  placeholder: "어디로 갈지 말해보세요",
  locationAskable: false,
  onChange: jest.fn(),
  onFocus: jest.fn(),
  onShoot: jest.fn(),
  onClearAttach: jest.fn(),
  onSubmit: jest.fn(),
  onAskLocation: jest.fn(),
};

function mount(props: Partial<React.ComponentProps<typeof TravelDock>> = {}) {
  let tree: renderer.ReactTestRenderer;
  act(() => {
    tree = renderer.create(<TravelDock {...base} {...props} />);
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
    .find((n) => typeof n.props.onPress === "function");
}

describe("TravelDock", () => {
  it("칩 줄 없이 입력 줄만 세운다 — 칩은 시트 밖에서 산다", () => {
    const tree = mount();

    expect(tree.root.findAllByProps({ testID: "travel-chip-row" })).toHaveLength(0);
    expect(byId(tree, "travel-send")).toBeDefined();
  });

  it("첨부가 있으면 입력 줄 위에 배너를 세운다", () => {
    const tree = mount({ photo });

    expect(texts(tree)).toContain("이 사진 같은 분위기로 찾아요");
    expect(tree.root.findAllByProps({ testID: "travel-attach-banner" }).length).toBeGreaterThan(0);
  });

  it("입력이 있으면 전송이 살아난다", () => {
    const onSubmit = jest.fn();
    const tree = mount({ value: "제주", onSubmit });
    const send = byId(tree, "travel-send")!;

    act(() => send.props.onPress());

    expect(send.props.disabled).toBe(false);
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("글자가 없어도 첨부만으로 전송이 살아난다", () => {
    const tree = mount({ value: "", photo });

    expect(byId(tree, "travel-send")!.props.disabled).toBe(false);
  });

  it("빈 입력에서는 전송을 막는다", () => {
    expect(byId(mount(), "travel-send")!.props.disabled).toBe(true);
  });

  it("응답을 기다리는 동안 입력을 잠근다", () => {
    const input = mount({ disabled: true }).root.findByType(TextInput);

    expect(input.props.editable).toBe(false);
  });

  it("입력 포커스를 시트로 알린다", () => {
    const onFocus = jest.fn();
    const input = mount({ onFocus }).root.findByType(TextInput);

    act(() => input.props.onFocus());

    expect(onFocus).toHaveBeenCalledTimes(1);
  });

  it("권한을 아직 묻지 않았을 때만 프라이머를 낸다", () => {
    expect(byId(mount(), "travel-ask-location")).toBeUndefined();
    expect(byId(mount({ locationAskable: true }), "travel-ask-location")).toBeDefined();
  });

  it("첨부 중에는 프라이머를 접어 도크를 두 행으로 묶는다", () => {
    const tree = mount({ locationAskable: true, photo });

    expect(byId(tree, "travel-ask-location")).toBeUndefined();
  });
});

describe("도크 스타일시트와 레이아웃 상수", () => {
  it("도크는 시트 안에서 흐름에 앉는다 — 절대 배치가 아니다", () => {
    expect(dockStyles.root).not.toHaveProperty("position");
    expect(dockStyles.root).not.toHaveProperty("bottom");
  });

  it("입력 줄 높이가 DOCK_FIELD_PX 와 같다", () => {
    expect(dockStyles.field.height).toBe(DOCK_FIELD_PX);
  });

  it("도크 하단 패딩이 DOCK_PAD_BOTTOM_PX 와 같다", () => {
    expect(dockStyles.root.paddingBottom).toBe(DOCK_PAD_BOTTOM_PX);
  });

  it("첨부 줄은 썸네일에 배너 패딩·테두리·아래 여백을 더한 값이다", () => {
    expect(
      dockStyles.attachThumb.height +
        dockStyles.attach.paddingVertical * 2 +
        dockStyles.attach.borderWidth * 2 +
        dockStyles.attach.marginBottom,
    ).toBe(DOCK_ATTACH_ROW_PX);
  });

  it("프라이머 줄은 프라이머 높이에 아래 여백을 더한 값이다", () => {
    expect(dockStyles.primer.height + dockStyles.primer.marginBottom).toBe(DOCK_PRIMER_PX);
  });
});
