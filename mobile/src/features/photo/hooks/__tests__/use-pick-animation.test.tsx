import { AccessibilityInfo, View } from "react-native";
import renderer, { act } from "react-test-renderer";
import { usePickAnimation } from "@/features/photo/hooks/use-pick-animation";

function Harness({
  status,
  onFinaleComplete,
}: {
  status: "idle" | "loading" | "success" | "error";
  onFinaleComplete: () => void;
}) {
  usePickAnimation(status, onFinaleComplete);
  return <View />;
}

describe("usePickAnimation", () => {
  beforeEach(() => {
    jest.useFakeTimers();
    jest.spyOn(AccessibilityInfo, "isReduceMotionEnabled").mockResolvedValue(false);
    jest
      .spyOn(AccessibilityInfo, "addEventListener")
      .mockReturnValue({ remove: jest.fn() } as unknown as ReturnType<
        typeof AccessibilityInfo.addEventListener
      >);
  });

  afterEach(() => {
    act(() => {
      jest.clearAllTimers();
    });
    jest.useRealTimers();
    jest.restoreAllMocks();
  });

  it("mounts while loading and unmounts without throwing (stops the hop loop)", async () => {
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<Harness status="loading" onFinaleComplete={() => {}} />);
    });
    expect(r!.toJSON()).not.toBeNull();
    await act(async () => {
      r!.unmount();
    });
  });

  it("calls onFinaleComplete without a loop when reduced motion is enabled", async () => {
    (AccessibilityInfo.isReduceMotionEnabled as jest.Mock).mockResolvedValue(true);
    const onFinaleComplete = jest.fn();
    await act(async () => {
      renderer.create(<Harness status="success" onFinaleComplete={onFinaleComplete} />);
    });
    expect(onFinaleComplete).toHaveBeenCalled();
  });
});
