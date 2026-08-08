import renderer, { act } from "react-test-renderer";
import { ScrollView, StyleSheet, Text, TextInput } from "react-native";
import {
  TravelDock,
  dockStyles,
  PHOTO_CHIP_LABEL,
  PHOTO_CHIP_TEST_ID,
} from "@/features/travel/components/TravelDock";
import {
  DOCK_ATTACH_ROW_PX,
  DOCK_CHIP_ROW_PX,
  DOCK_FIELD_PX,
  DOCK_PAD_BOTTOM_PX,
  DOCK_PRIMER_PX,
} from "@/features/travel/lib/screen-layout";
import type { DockChip } from "@/features/travel/lib/dock-chips";

const chips: DockChip[] = [
  { kind: "photo" },
  { kind: "context", title: "성산일출봉", expanded: false },
  { kind: "query", chip: { kind: "question", label: "사람 적은 곳만", question: "사람 적은 곳" } },
];

const photo = { uri: "file://a.jpg", name: "a.jpg", type: "image/jpeg" };

const base = {
  value: "",
  photo: null,
  chips,
  disabled: false,
  placeholder: "어디로 갈지 말해보세요",
  locationAskable: false,
  bottom: 83,
  onChange: jest.fn(),
  onChipPress: jest.fn(),
  onShoot: jest.fn(),
  onClearAttach: jest.fn(),
  onSubmit: jest.fn(),
  onFocus: jest.fn(),
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

function pressableChip(tree: renderer.ReactTestRenderer, testID: string) {
  return tree.root
    .findAllByProps({ testID })
    .find((node) => typeof node.props.style === "function");
}

function chipOpacity(tree: renderer.ReactTestRenderer): number | undefined {
  const host = tree.root
    .findAllByProps({ testID: PHOTO_CHIP_TEST_ID })
    .find((node) => typeof node.type === "string");
  return StyleSheet.flatten(host?.props.style)?.opacity as number | undefined;
}

describe("TravelDock", () => {
  it("칩을 순서대로 그린다", () => {
    const shown = texts(mount());

    expect(shown).toContain("사진");
    expect(shown).toContain("성산일출봉");
    expect(shown).toContain("사람 적은 곳만");
    expect(shown.indexOf("사진")).toBeLessThan(shown.indexOf("성산일출봉"));
    expect(shown.indexOf("성산일출봉")).toBeLessThan(shown.indexOf("사람 적은 곳만"));
  });

  it("접힌 맥락 칩은 근처를 붙이고 펼친 칩은 이름만 쓴다", () => {
    const collapsed = mount({ chips: [{ kind: "context", title: "성산일출봉", expanded: false }] });
    const expanded = mount({ chips: [{ kind: "context", title: "성산일출봉", expanded: true }] });

    expect(texts(collapsed)).toBe("성산일출봉 근처");
    expect(texts(expanded)).toBe("성산일출봉");
  });

  it("사진 칩은 스크롤 트랙 밖에 고정으로 남는다", () => {
    const tree = mount();
    const track = tree.root.findByType(ScrollView);

    expect(byId(tree, PHOTO_CHIP_TEST_ID)).toBeDefined();
    expect(track.findAllByProps({ testID: PHOTO_CHIP_TEST_ID })).toHaveLength(0);
    expect(
      track
        .findAll((node) => node.props.accessibilityRole === "button")
        .map((node) => node.props.accessibilityLabel),
    ).not.toContain(PHOTO_CHIP_LABEL);
  });

  it("고정 사진 칩을 누르면 사진 칩을 그대로 올린다", () => {
    const onChipPress = jest.fn();
    const tree = mount({ onChipPress });

    act(() => byId(tree, PHOTO_CHIP_TEST_ID)!.props.onPress());

    expect(onChipPress).toHaveBeenCalledWith({ kind: "photo" });
  });

  it("스크롤 칩은 사진 칩을 뺀 자리로 번호를 매긴다", () => {
    const onChipPress = jest.fn();
    const tree = mount({ onChipPress });

    act(() => byId(tree, "travel-chip-0")!.props.onPress());

    expect(onChipPress).toHaveBeenCalledWith(chips[1]);
  });

  it("사진 칩이 없는 상태에서는 고정 자리도 비운다", () => {
    const tree = mount({ chips: [{ kind: "context", title: "성산일출봉", expanded: true }] });

    expect(byId(tree, PHOTO_CHIP_TEST_ID)).toBeUndefined();
    expect(byId(tree, "travel-chip-0")).toBeDefined();
  });

  it("첨부가 있으면 배너가 칩 행을 대신한다", () => {
    const tree = mount({ photo });

    expect(texts(tree)).toContain("이 사진 같은 분위기로 찾아요");
    expect(texts(tree)).not.toContain("사람 적은 곳만");
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

  it("응답을 기다리는 동안 고정 칩과 스크롤 칩을 함께 잠근다", () => {
    const locked = mount({ disabled: true });

    expect(pressableChip(locked, PHOTO_CHIP_TEST_ID)?.props.disabled).toBe(true);
    expect(pressableChip(locked, "travel-chip-0")?.props.disabled).toBe(true);
    expect(pressableChip(mount(), PHOTO_CHIP_TEST_ID)?.props.disabled).toBe(false);
  });

  it("잠긴 칩은 눌리지 않아도 흐리게 보인다", () => {
    expect(chipOpacity(mount({ disabled: true }))).toBe(dockStyles.pressed.opacity);
    expect(chipOpacity(mount())).toBeUndefined();
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
  it("입력 줄 높이가 DOCK_FIELD_PX 와 같다", () => {
    expect(dockStyles.field.height).toBe(DOCK_FIELD_PX);
  });

  it("도크 하단 패딩이 DOCK_PAD_BOTTOM_PX 와 같다", () => {
    expect(dockStyles.root.paddingBottom).toBe(DOCK_PAD_BOTTOM_PX);
  });

  it("칩 줄은 칩 높이에 칩 밴드 아래 여백을 더한 값이다", () => {
    expect(dockStyles.chip.height + dockStyles.chipBand.marginBottom).toBe(DOCK_CHIP_ROW_PX);
  });

  it("고정 칩과 스크롤 트랙 어느 쪽도 칩 줄을 더 키우지 않는다", () => {
    expect(dockStyles.chipBand.alignItems).toBe("flex-start");
    expect(dockStyles.chipTrack.flexGrow).toBe(0);
    expect(dockStyles.chipTrack.flexShrink).toBe(1);
    expect(dockStyles.chips).not.toHaveProperty("paddingBottom");
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
