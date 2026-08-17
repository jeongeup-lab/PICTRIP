import renderer, { act } from "react-test-renderer";
import { CategoryChips } from "@/features/home/components/CategoryChips";

describe("CategoryChips", () => {
  it("marks the active chip and reports selection changes", async () => {
    const onChange = jest.fn();
    let tree: renderer.ReactTestRenderer;
    await act(async () => {
      tree = renderer.create(<CategoryChips selected={null} onChange={onChange} />);
    });

    const all = tree!.root.findByProps({ testID: "rank-category-all" });
    expect(all.props.accessibilityState.selected).toBe(true);

    await act(async () => {
      tree!.root.findByProps({ testID: "rank-category-CAFE" }).props.onPress();
    });
    expect(onChange).toHaveBeenCalledWith("CAFE");
  });

  it("returns to the full mix when 전체 is tapped", async () => {
    const onChange = jest.fn();
    let tree: renderer.ReactTestRenderer;
    await act(async () => {
      tree = renderer.create(<CategoryChips selected="FOOD" onChange={onChange} />);
    });

    expect(
      tree!.root.findByProps({ testID: "rank-category-FOOD" }).props.accessibilityState.selected,
    ).toBe(true);

    await act(async () => {
      tree!.root.findByProps({ testID: "rank-category-all" }).props.onPress();
    });
    expect(onChange).toHaveBeenCalledWith(null);
  });
});
