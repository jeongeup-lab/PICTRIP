import renderer, { act } from "react-test-renderer";
import { Icon } from "@/components/Icon";

describe("Icon", () => {
  it("renders a known icon without crashing", async () => {
    let r: renderer.ReactTestRenderer;
    // react-test-renderer 19.2 flushes renders on a macrotask; an async act()
    // is required to drain the scheduler before reading toJSON().
    await act(async () => {
      r = renderer.create(<Icon name="chevron-left" />);
    });
    const tree = r!.toJSON();
    expect(tree).toBeTruthy();
  });

  it.each(["image", "sparkle"] as const)("renders %s", async (name) => {
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<Icon name={name} />);
    });
    expect(r!.toJSON()).toBeTruthy();
  });
});
