import renderer, { act } from "react-test-renderer";
import { CongestionChip } from "@/components/CongestionChip";

describe("CongestionChip", () => {
  it("renders nothing when level is null", async () => {
    let r: renderer.ReactTestRenderer;
    // react-test-renderer 19.2 flushes renders on a macrotask; an async act()
    // is required to drain the scheduler before reading toJSON().
    await act(async () => {
      r = renderer.create(<CongestionChip level={null} />);
    });
    const tree = r!.toJSON();
    expect(tree).toBeNull();
  });
  it("renders a label when level is set", async () => {
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<CongestionChip level="high" />);
    });
    const tree = r!.toJSON();
    expect(JSON.stringify(tree)).toContain("혼잡");
  });
});
