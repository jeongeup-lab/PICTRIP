import renderer, { act } from "react-test-renderer";
import { ScrollView, StyleSheet, Text } from "react-native";
import {
  ChipRow,
  chipStyles,
  PHOTO_CHIP_LABEL,
  PHOTO_CHIP_TEST_ID,
} from "@/features/travel/components/ChipRow";
import type { DockChip } from "@/features/travel/lib/dock-chips";
import { spacing } from "@/constants/theme";

const chips: DockChip[] = [
  { kind: "photo" },
  { kind: "query", chip: { kind: "anchor", label: "성산일출봉 근처 카페", action: "cafe" } },
  { kind: "query", chip: { kind: "anchor", label: "성산일출봉 근처 맛집", action: "food" } },
];

const base = { chips, disabled: false, inset: false, onChipPress: jest.fn() };

function mount(props: Partial<React.ComponentProps<typeof ChipRow>> = {}) {
  let tree: renderer.ReactTestRenderer;
  act(() => {
    tree = renderer.create(<ChipRow {...base} {...props} />);
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

describe("ChipRow", () => {
  it("칩을 넘겨준 순서대로 그린다", () => {
    const shown = texts(mount());

    expect(shown.indexOf(PHOTO_CHIP_LABEL)).toBeLessThan(shown.indexOf("성산일출봉 근처 카페"));
    expect(shown.indexOf("성산일출봉 근처 카페")).toBeLessThan(
      shown.indexOf("성산일출봉 근처 맛집"),
    );
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

  it("사진 칩이 없는 목록에서는 고정 자리도 비운다", () => {
    const tree = mount({ chips: chips.slice(1) });

    expect(byId(tree, PHOTO_CHIP_TEST_ID)).toBeUndefined();
    expect(byId(tree, "travel-chip-0")).toBeDefined();
  });

  it("칩이 하나도 없으면 줄 자체를 그리지 않는다", () => {
    expect(mount({ chips: [] }).root.findAllByProps({ testID: "travel-chip-row" })).toHaveLength(0);
  });

  it("잠기면 고정 칩과 스크롤 칩을 함께 잠근다", () => {
    const locked = mount({ disabled: true });

    expect(pressableChip(locked, PHOTO_CHIP_TEST_ID)?.props.disabled).toBe(true);
    expect(pressableChip(locked, "travel-chip-0")?.props.disabled).toBe(true);
    expect(pressableChip(mount(), PHOTO_CHIP_TEST_ID)?.props.disabled).toBe(false);
  });

  it("잠긴 칩은 눌리지 않아도 흐리게 보인다", () => {
    const host = (tree: renderer.ReactTestRenderer) =>
      tree.root
        .findAllByProps({ testID: PHOTO_CHIP_TEST_ID })
        .find((node) => typeof node.type === "string");

    expect(StyleSheet.flatten(host(mount({ disabled: true }))?.props.style)?.opacity).toBe(
      chipStyles.pressed.opacity,
    );
    expect(StyleSheet.flatten(host(mount())?.props.style)?.opacity).toBeUndefined();
  });

  it("패널 안에서는 카드와 같은 안쪽 여백을 쓴다", () => {
    const row = (tree: renderer.ReactTestRenderer) =>
      StyleSheet.flatten(tree.root.findByProps({ testID: "travel-chip-row" }).props.style);

    expect(row(mount({ inset: true })).paddingHorizontal).toBe(spacing.md);
    expect(row(mount()).paddingHorizontal).toBeUndefined();
  });
});

describe("칩 스타일시트", () => {
  it("고정 칩과 스크롤 트랙 어느 쪽도 칩 줄을 더 키우지 않는다", () => {
    expect(chipStyles.band.alignItems).toBe("flex-start");
    expect(chipStyles.track.flexGrow).toBe(0);
    expect(chipStyles.track.flexShrink).toBe(1);
    expect(chipStyles.chips).not.toHaveProperty("paddingBottom");
  });
});
