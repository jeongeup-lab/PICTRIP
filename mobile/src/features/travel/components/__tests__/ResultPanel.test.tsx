import renderer, { act } from "react-test-renderer";
import { StyleSheet, Text } from "react-native";
import { ResultPanel, panelStyles } from "@/features/travel/components/ResultPanel";
import { PANEL_PAD_PX } from "@/features/travel/lib/screen-layout";

function mount(bottom: number) {
  let tree: renderer.ReactTestRenderer;
  act(() => {
    tree = renderer.create(
      <ResultPanel bottom={bottom}>
        <Text>답변</Text>
      </ResultPanel>,
    );
  });
  return tree!;
}

describe("ResultPanel", () => {
  it("독 위에 앉을 높이를 그대로 받는다", () => {
    const style = StyleSheet.flatten(
      mount(58).root.findByProps({ testID: "travel-result-panel" }).props.style,
    );

    expect(style.bottom).toBe(58);
    expect(style.position).toBe("absolute");
  });

  it("지도 탭이 패널 옆을 지나가도록 상자를 비워 둔다", () => {
    expect(mount(58).root.findByProps({ testID: "travel-result-panel" }).props.pointerEvents).toBe(
      "box-none",
    );
  });

  it("불투명한 바탕을 깐다 — 밝은 지도 위에서 글씨가 뭉개지지 않게", () => {
    const style = StyleSheet.flatten(
      mount(58).root.findByProps({ testID: "travel-result-panel" }).props.style,
    );

    expect(String(style.backgroundColor)).not.toContain("rgba");
  });
});

describe("패널 스타일시트와 레이아웃 상수", () => {
  it("PANEL_PAD_PX 는 패널 위아래 여백과 테두리를 합한 값이다", () => {
    expect(
      panelStyles.root.paddingTop +
        panelStyles.root.paddingBottom +
        panelStyles.root.borderWidth * 2,
    ).toBe(PANEL_PAD_PX);
  });
});
