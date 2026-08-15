import renderer, { act } from "react-test-renderer";
import { Text } from "react-native";
import AccountDeleteScreen from "@/app/account/delete";
import { DeleteConfirmSheet } from "@/features/auth/components/DeleteConfirmSheet";
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

const expoRouterMock = jest.requireMock<{
  router: { back: jest.Mock; canGoBack: jest.Mock; replace: jest.Mock; dismissAll: jest.Mock };
}>("expo-router");
const usePreventRemove = jest.requireMock<{ usePreventRemove: jest.Mock }>(
  "expo-router/react-navigation",
).usePreventRemove;

const deleteAccount = jest.fn(async (_reason?: string) => {});
const user: User = {
  id: 7,
  displayName: "이신성",
  email: "sinseong@example.com",
  avatarUrl: null,
  isOnboarded: true,
  createdAt: "2026-03-14T09:00:00Z",
};

const textOf = (tree: renderer.ReactTestRenderer) =>
  tree.root
    .findAllByType(Text)
    .map((node) => JSON.stringify(node.props.children))
    .join("|");

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

  const mount = async () => {
    await act(async () => {
      mounted = renderer.create(<AccountDeleteScreen />);
    });
    if (mounted === null) throw new Error("screen did not mount");
    return mounted;
  };

  it("asks for a reason without warning on the screen itself", async () => {
    const tree = await mount();
    const shown = textOf(tree);

    expect(shown).toContain("떠나시는 이유 (선택)");
    expect(shown).toContain("가고 싶던 곳을 다 찾았어요");
    expect(shown).not.toContain("되돌릴 수 없어요");
    expect(tree.root.findByProps({ testID: "delete-account" }).props.disabled).toBe(false);
  });

  it("confirms in a sheet before deleting and sends the chosen reason once", async () => {
    const tree = await mount();
    expect(tree.root.findByType(DeleteConfirmSheet).props.visible).toBe(false);

    await act(async () => {
      tree.root.findByProps({ testID: "delete-reason-taking_a_break" }).props.onPress();
    });
    await act(async () => {
      tree.root.findByProps({ testID: "delete-account" }).props.onPress();
    });
    expect(tree.root.findByType(DeleteConfirmSheet).props.visible).toBe(true);
    expect(textOf(tree)).toContain("계정과 저장한 장소가 모두 삭제돼요. 되돌릴 수 없어요.");

    await act(async () => {
      tree.root.findByProps({ testID: "delete-confirm" }).props.onPress();
      tree.root.findByProps({ testID: "delete-confirm" }).props.onPress();
    });

    expect(deleteAccount).toHaveBeenCalledTimes(1);
    expect(deleteAccount).toHaveBeenCalledWith("taking_a_break");
    expect(expoRouterMock.router.dismissAll).toHaveBeenCalled();
    expect(expoRouterMock.router.replace).toHaveBeenCalledWith("/(tabs)");
  });

  it("deletes without a reason when none is chosen", async () => {
    const tree = await mount();

    await act(async () => {
      tree.root.findByProps({ testID: "delete-account" }).props.onPress();
    });
    await act(async () => {
      tree.root.findByProps({ testID: "delete-confirm" }).props.onPress();
    });

    expect(deleteAccount).toHaveBeenCalledWith(undefined);
  });

  it("lets a second tap on the same reason clear it", async () => {
    const tree = await mount();

    await act(async () => {
      tree.root.findByProps({ testID: "delete-reason-declined" }).props.onPress();
    });
    await act(async () => {
      tree.root.findByProps({ testID: "delete-reason-declined" }).props.onPress();
    });
    await act(async () => {
      tree.root.findByProps({ testID: "delete-account" }).props.onPress();
    });
    await act(async () => {
      tree.root.findByProps({ testID: "delete-confirm" }).props.onPress();
    });

    expect(deleteAccount).toHaveBeenCalledWith(undefined);
  });

  it("keeps the sheet open and shows the reason when deletion fails", async () => {
    const { AppError } = jest.requireActual<typeof import("@/lib/app-error")>("@/lib/app-error");
    deleteAccount.mockRejectedValueOnce(new AppError("NETWORK_ERROR", "boom", 0));
    const tree = await mount();

    await act(async () => {
      tree.root.findByProps({ testID: "delete-account" }).props.onPress();
    });
    await act(async () => {
      tree.root.findByProps({ testID: "delete-confirm" }).props.onPress();
    });

    expect(tree.root.findByType(DeleteConfirmSheet).props.visible).toBe(true);
    expect(textOf(tree)).toContain("네트워크가 불안정해요. 잠시 후 다시 시도해 주세요.");
    expect(expoRouterMock.router.dismissAll).not.toHaveBeenCalled();
  });

  it("prevents removal only while account deletion is in flight", async () => {
    let resolveDelete: (() => void) | undefined;
    deleteAccount.mockImplementationOnce(
      () =>
        new Promise<void>((resolve) => {
          resolveDelete = resolve;
        }),
    );
    const tree = await mount();
    expect(usePreventRemove).toHaveBeenLastCalledWith(false, expect.any(Function));

    await act(async () => {
      tree.root.findByProps({ testID: "delete-account" }).props.onPress();
    });
    await act(async () => {
      tree.root.findByProps({ testID: "delete-confirm" }).props.onPress();
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
    expect(textOf(mounted)).toContain("로그인이 필요해요");
  });
});
