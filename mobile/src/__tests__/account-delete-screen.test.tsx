import renderer, { act } from "react-test-renderer";
import { Text } from "react-native";
import AccountDeleteScreen from "@/app/account/delete";
import { useAuthStore } from "@/features/auth/stores/auth-store";
import type { User } from "@/lib/api-types";

jest.mock("expo-router", () => {
  const nav = {
    addListener: jest.fn(() => jest.fn()),
    dispatch: jest.fn(),
  };
  return {
    router: { back: jest.fn(), canGoBack: jest.fn(), replace: jest.fn(), dismissAll: jest.fn() },
    useNavigation: () => nav,
  };
});
jest.mock("expo-router/react-navigation", () => ({ usePreventRemove: jest.fn() }));
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
jest.mock("@/features/saved/queries", () => ({
  useSavedList: jest.fn(() => ({ data: [{ contentId: "1" }] })),
}));

const expoRouterMock = jest.requireMock<{
  router: { back: jest.Mock; canGoBack: jest.Mock; replace: jest.Mock; dismissAll: jest.Mock };
}>("expo-router");
const usePreventRemove = jest.requireMock<{ usePreventRemove: jest.Mock }>(
  "expo-router/react-navigation",
).usePreventRemove;

const deleteAccount = jest.fn(async () => {});
const user: User = {
  id: 7,
  displayName: "이신성",
  email: "sinseong@example.com",
  avatarUrl: null,
  isOnboarded: true,
  createdAt: "2026-03-14T09:00:00Z",
};

describe("AccountDeleteScreen", () => {
  let mounted: renderer.ReactTestRenderer | null = null;

  beforeEach(() => {
    useAuthStore.setState({ user, isAuthenticated: true, accessToken: "token", deleteAccount });
  });

  afterEach(async () => {
    await act(async () => {
      mounted?.unmount();
    });
    mounted = null;
    jest.clearAllMocks();
  });

  it("requires acknowledgement before a direct account deletion", async () => {
    await act(async () => {
      mounted = renderer.create(<AccountDeleteScreen />);
    });
    if (mounted === null) throw new Error("screen did not mount");
    const deleteButton = mounted.root.findByProps({ testID: "delete-account" });
    expect(deleteButton.props.disabled).toBe(true);

    await act(async () => {
      mounted?.root.findByProps({ testID: "delete-acknowledgement" }).props.onPress();
    });
    await act(async () => {
      mounted?.root.findByProps({ testID: "delete-account" }).props.onPress();
      mounted?.root.findByProps({ testID: "delete-account" }).props.onPress();
    });

    expect(deleteAccount).toHaveBeenCalledTimes(1);
    expect(expoRouterMock.router.dismissAll).toHaveBeenCalled();
    expect(expoRouterMock.router.replace).toHaveBeenCalledWith("/(tabs)");
  });

  it("states the loss in one line and names each item once", async () => {
    await act(async () => {
      mounted = renderer.create(<AccountDeleteScreen />);
    });
    if (mounted === null) throw new Error("screen did not mount");

    expect(mounted.root.findByProps({ testID: "delete-consequences" })).toBeDefined();
    const shown = mounted.root
      .findAllByType(Text)
      .map((node) => JSON.stringify(node.props.children))
      .join("|");
    expect(shown).toContain("탈퇴하면 되돌릴 수 없어요.");
    expect(shown).toContain("저장한 장소 1곳");
    expect(shown).toContain("취향에 맞춘 추천");
    expect(shown).toContain("계정 정보와 로그인 연결");
    expect(shown).not.toContain("PicTrip에 저장된");
  });

  it("prevents removal only while account deletion is in flight", async () => {
    let resolveDelete: (() => void) | undefined;
    deleteAccount.mockImplementationOnce(
      () =>
        new Promise<void>((resolve) => {
          resolveDelete = resolve;
        }),
    );
    await act(async () => {
      mounted = renderer.create(<AccountDeleteScreen />);
    });
    if (mounted === null) throw new Error("screen did not mount");
    expect(usePreventRemove).toHaveBeenLastCalledWith(false, expect.any(Function));
    await act(async () => {
      mounted?.root.findByProps({ testID: "delete-acknowledgement" }).props.onPress();
    });
    await act(async () => {
      mounted?.root.findByProps({ testID: "delete-account" }).props.onPress();
    });

    expect(usePreventRemove).toHaveBeenLastCalledWith(true, expect.any(Function));
    expect(expoRouterMock.router.dismissAll).not.toHaveBeenCalled();

    await act(async () => {
      resolveDelete?.();
    });
    expect(usePreventRemove).toHaveBeenLastCalledWith(false, expect.any(Function));
    expect(expoRouterMock.router.dismissAll).toHaveBeenCalledTimes(1);
    expect(expoRouterMock.router.replace).toHaveBeenCalledWith("/(tabs)");
  });

  it("sends guests back to account without exposing deletion", async () => {
    await act(async () => {
      useAuthStore.setState({ user: null, isAuthenticated: false, accessToken: null });
      mounted = renderer.create(<AccountDeleteScreen />);
    });
    if (mounted === null) throw new Error("screen did not mount");

    expect(mounted.root.findAllByProps({ testID: "delete-account" })).toHaveLength(0);
    const shown = mounted.root
      .findAllByType(Text)
      .map((node) => JSON.stringify(node.props.children))
      .join("|");
    expect(shown).toContain("로그인이 필요해요");
  });
});
