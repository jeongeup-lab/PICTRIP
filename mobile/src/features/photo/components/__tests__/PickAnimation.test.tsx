import { AccessibilityInfo } from "react-native";
import renderer, { act } from "react-test-renderer";
import { PickAnimation } from "@/features/photo/components/PickAnimation";
import type { PickedImage } from "@/features/photo/usecases/pick-image";

const asset: PickedImage = {
  uri: "file:///photo.jpg",
  mimeType: "image/jpeg",
  fileName: "photo.jpg",
};

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

describe("PickAnimation", () => {
  it.each(["idle", "loading", "success", "error"] as const)(
    "renders without throwing for status=%s",
    async (status) => {
      let r: renderer.ReactTestRenderer;
      await act(async () => {
        r = renderer.create(
          <PickAnimation asset={asset} status={status} onFinaleComplete={() => {}} />,
        );
      });
      expect(r!.toJSON()).not.toBeNull();
      await act(async () => {
        r!.unmount();
      });
    },
  );

  it("renders with no asset without throwing", async () => {
    await act(async () => {
      renderer.create(<PickAnimation asset={null} status="loading" onFinaleComplete={() => {}} />);
    });
  });
});
