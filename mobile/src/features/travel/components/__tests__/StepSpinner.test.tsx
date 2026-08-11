import { Animated } from "react-native";
import renderer, { act } from "react-test-renderer";
import { SPINNER_TEST_ID, StepSpinner } from "@/features/travel/components/StepSpinner";

describe("StepSpinner", () => {
  it("응답을 기다리는 동안 계속 도는 루프를 시작한다", () => {
    const loop = jest.spyOn(Animated, "loop");

    let tree: renderer.ReactTestRenderer | undefined;
    act(() => {
      tree = renderer.create(<StepSpinner />);
    });

    expect(loop).toHaveBeenCalledTimes(1);
    act(() => tree?.unmount());
    loop.mockRestore();
  });

  it("화면에서 사라지면 루프를 멈춘다", () => {
    const stop = jest.fn();
    const loop = jest
      .spyOn(Animated, "loop")
      .mockReturnValue({ start: jest.fn(), stop, reset: jest.fn() } as never);

    let tree: renderer.ReactTestRenderer | undefined;
    act(() => {
      tree = renderer.create(<StepSpinner />);
    });
    act(() => tree?.unmount());

    expect(stop).toHaveBeenCalled();
    loop.mockRestore();
  });

  it("회전 변형을 단 원을 그린다", () => {
    let tree: renderer.ReactTestRenderer | undefined;
    act(() => {
      tree = renderer.create(<StepSpinner size={20} />);
    });

    const ring = tree!.root.findByProps({ testID: SPINNER_TEST_ID });
    const style = Array.isArray(ring.props.style) ? ring.props.style.flat() : [ring.props.style];
    const sized = style.find((entry: Record<string, unknown>) => entry?.width === 20);
    const spun = style.find((entry: Record<string, unknown>) => entry?.transform);

    expect(sized).toBeTruthy();
    expect(sized.borderRadius).toBe(10);
    expect(spun).toBeTruthy();
    act(() => tree?.unmount());
  });

  it("스크린리더에 진행 중임을 알린다", () => {
    let tree: renderer.ReactTestRenderer | undefined;
    act(() => {
      tree = renderer.create(<StepSpinner />);
    });

    const ring = tree!.root.findByProps({ testID: SPINNER_TEST_ID });
    expect(ring.props.accessibilityRole).toBe("progressbar");
    act(() => tree?.unmount());
  });
});
