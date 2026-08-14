import renderer, { act } from "react-test-renderer";
import { router } from "expo-router";
import { ScreenHeader } from "@/components/ScreenHeader";

jest.mock("expo-router", () => ({
  router: { back: jest.fn(), canGoBack: jest.fn(), replace: jest.fn() },
}));

describe("ScreenHeader", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });
  it("goes back when a navigation history exists", async () => {
    jest.mocked(router.canGoBack).mockReturnValue(true);
    let tree: renderer.ReactTestRenderer | null = null;
    await act(async () => {
      tree = renderer.create(<ScreenHeader title="기기 권한" fallback="/settings" />);
    });

    await act(async () => {
      tree?.root.findByProps({ testID: "screen-header-back" }).props.onPress();
    });

    expect(router.back).toHaveBeenCalledTimes(1);
    expect(router.replace).not.toHaveBeenCalled();
  });

  it("replaces with the fallback when there is no navigation history", async () => {
    jest.mocked(router.canGoBack).mockReturnValue(false);
    let tree: renderer.ReactTestRenderer | null = null;
    await act(async () => {
      tree = renderer.create(<ScreenHeader title="기기 권한" fallback="/settings" />);
    });

    await act(async () => {
      tree?.root.findByProps({ testID: "screen-header-back" }).props.onPress();
    });

    expect(router.replace).toHaveBeenCalledWith("/settings");
  });

  it("blocks navigation while the screen owns a pending action", async () => {
    jest.mocked(router.canGoBack).mockReturnValue(true);
    const holder: { tree: renderer.ReactTestRenderer | null } = { tree: null };
    await act(async () => {
      holder.tree = renderer.create(
        <ScreenHeader title="회원 탈퇴" fallback="/account" disabled />,
      );
    });

    if (holder.tree === null) throw new Error("header did not mount");
    const button = holder.tree.root.findByProps({ testID: "screen-header-back" });
    expect(button.props.disabled).toBe(true);
    expect(button.props.accessibilityState).toEqual({ disabled: true });

    await act(async () => {
      button.props.onPress();
    });
    expect(router.back).not.toHaveBeenCalled();
    expect(router.replace).not.toHaveBeenCalled();
  });
});
