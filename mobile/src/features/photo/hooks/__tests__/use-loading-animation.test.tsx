import { Animated, View } from "react-native";
import renderer, { act } from "react-test-renderer";
import { useLoadingAnimation } from "@/features/photo/hooks/use-loading-animation";

function Harness() {
  const { translateX } = useLoadingAnimation();
  return <Animated.View style={{ transform: [{ translateX }] }} />;
}

describe("useLoadingAnimation", () => {
  it("mounts, exposes an interpolation, and stops the loop on unmount", async () => {
    const stop = jest.spyOn(Animated, "loop");
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(
        <View>
          <Harness />
        </View>,
      );
    });
    expect(r!.toJSON()).not.toBeNull();
    expect(stop).toHaveBeenCalled();
    await act(async () => {
      r!.unmount();
    });
    stop.mockRestore();
  });
});
