import renderer, { act } from "react-test-renderer";
import { Text } from "react-native";
import { router } from "expo-router";
import AccountDeleteScreen from "@/app/account/delete";
import { useAuthStore } from "@/features/auth/stores/auth-store";
import type { User } from "@/lib/api-types";

jest.mock("expo-router", () => {
  const listener: { current?: (event: { preventDefault: () => void }) => void } = {};
  const nav = {
    addListener: jest.fn((_type: string, cb: (event: { preventDefault: () => void }) => void) => {
      listener.current = cb;
      return jest.fn();
    }),
  };
  return {
    router: { back: jest.fn(), canGoBack: jest.fn(), replace: jest.fn(), dismissAll: jest.fn() },
    useNavigation: () => nav,
    __listener: listener,
  };
});
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
jest.mock("@/features/saved/queries", () => ({
  useSavedList: jest.fn(() => ({ data: [{ contentId: "1" }] })),
}));

const expoRouterMock = jest.requireMock<{
  router: { back: jest.Mock; canGoBack: jest.Mock; replace: jest.Mock; dismissAll: jest.Mock };
  __listener: { current?: (event: { preventDefault: () => void }) => void };
}>("expo-router");

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

  it("blocks route removal while deletion is pending", async () => {
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
    await act(async () => {
      mounted?.root.findByProps({ testID: "delete-acknowledgement" }).props.onPress();
    });
    await act(async () => {
      mounted?.root.findByProps({ testID: "delete-account" }).props.onPress();
    });

    const preventDefault = jest.fn();
    await act(async () => {
      expoRouterMock.__listener.current?.({ preventDefault });
    });
    expect(preventDefault).toHaveBeenCalled();
    expect(expoRouterMock.router.dismissAll).not.toHaveBeenCalled();

    await act(async () => {
      resolveDelete?.();
    });
    await act(async () => {
      const preventDefaultAfter = jest.fn();
      expoRouterMock.__listener.current?.({ preventDefault: preventDefaultAfter });
      expect(preventDefaultAfter).not.toHaveBeenCalled();
    });
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
