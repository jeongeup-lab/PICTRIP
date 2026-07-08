import renderer, { act } from "react-test-renderer";
import { Text } from "react-native";
import { CurationIntro } from "@/features/curation/components/CurationIntro";

const layoutEvent = (lineCount: number) => ({
  nativeEvent: { lines: Array.from({ length: lineCount }, () => ({})) },
});

const introText = () => "오름과 해변, 골목 카페까지 카메라를 어디에 둬도 그림이 되는 제주.";

describe("CurationIntro", () => {
  let tree: renderer.ReactTestRenderer | null = null;

  afterEach(() => {
    act(() => tree?.unmount());
    tree = null;
  });

  it("clamps to 3 lines once measured over 3 lines, and toggles open/closed via the chevron", async () => {
    await act(async () => {
      tree = renderer.create(<CurationIntro intro={introText()} />);
    });
    const root = tree!.root;

    // Before measurement: unclamped (measuring pass).
    expect(root.findByType(Text).props.numberOfLines).toBeUndefined();

    // Measured at 5 lines → clamped to 3, chevron shown.
    await act(async () => {
      root.findByType(Text).props.onTextLayout(layoutEvent(5));
    });
    expect(root.findByType(Text).props.numberOfLines).toBe(3);
    const toggle = root.findByProps({ testID: "intro-toggle" });

    // Expand → full intro.
    await act(async () => {
      toggle.props.onPress();
    });
    expect(root.findByType(Text).props.numberOfLines).toBeUndefined();

    // Collapse again → back to 3 lines.
    await act(async () => {
      root.findByProps({ testID: "intro-toggle" }).props.onPress();
    });
    expect(root.findByType(Text).props.numberOfLines).toBe(3);
  });

  it("hides the chevron when the intro fits in 3 lines", async () => {
    await act(async () => {
      tree = renderer.create(<CurationIntro intro={introText()} />);
    });
    const root = tree!.root;

    await act(async () => {
      root.findByType(Text).props.onTextLayout(layoutEvent(2));
    });
    expect(root.findAllByProps({ testID: "intro-toggle" })).toHaveLength(0);
    expect(root.findByType(Text).props.numberOfLines).toBeUndefined();
  });
});
