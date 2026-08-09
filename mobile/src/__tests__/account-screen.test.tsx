import renderer, { act } from "react-test-renderer";
import { Alert, Text } from "react-native";
import AccountScreen from "@/app/account";
import { useAuthStore } from "@/features/auth/stores/auth-store";
import { AppError } from "@/lib/app-error";
import type { User } from "@/lib/api-types";

jest.mock("expo-router", () => ({ router: { push: jest.fn(), back: jest.fn() } }));
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
jest.mock("@/features/saved/queries", () => ({
  useSavedList: jest.fn(() => ({ data: [{ contentId: "1" }, { contentId: "2" }] })),
}));

const alertSpy = jest.spyOn(Alert, "alert").mockImplementation(() => undefined);

const tapAlertButton = async (label: string) => {
  const buttons = alertSpy.mock.calls.at(-1)?.[2] ?? [];
  const button = buttons.find((b) => b.text === label);
  await act(async () => {
    button?.onPress?.();
  });
};

const logout = jest.fn(async () => undefined);
const deleteAccount = jest.fn(async () => undefined);

const USER: User = {
  id: 7,
  displayName: "이신성",
  email: "sinseong@example.com",
  avatarUrl: null,
  isOnboarded: true,
  createdAt: "2026-03-14T09:00:00Z",
};

let mounted: renderer.ReactTestRenderer | null = null;

async function mount() {
  await act(async () => {
    mounted = renderer.create(<AccountScreen />);
  });
  return mounted!;
}

const press = async (tree: renderer.ReactTestRenderer, testID: string) => {
  const target = tree.root.findAll((n) => n.props.testID === testID && !!n.props.onPress)[0];
  await act(async () => {
    target.props.onPress();
  });
};

const texts = (tree: renderer.ReactTestRenderer) =>
  tree.root.findAllByType(Text).map((node) => JSON.stringify(node.props.children));

beforeEach(() => {
  useAuthStore.setState({
    user: USER,
    isAuthenticated: true,
    accessToken: "token",
    logout,
    deleteAccount,
  });
});

afterEach(async () => {
  await act(async () => {
    mounted?.unmount();
  });
  mounted = null;
  jest.clearAllMocks();
});

describe("AccountScreen", () => {
  it("shows the profile facts the server actually returns", async () => {
    const tree = await mount();
    const shown = texts(tree).join("|");
    expect(shown).toContain("이신성");
    expect(shown).toContain("sinseong@example.com");
    expect(shown).toContain("2026.03.14");
  });

  it("names what is lost, with the real scrap count", async () => {
    const tree = await mount();
    expect(tree.root.findAllByProps({ testID: "delete-confirm" })).toHaveLength(0);

    await press(tree, "open-delete");
    const shown = texts(tree).join("|");
    expect(shown).toContain("스크랩 2개가 삭제돼요");
    expect(shown).toContain("소셜 로그인 연결이 해제돼요");
  });

  it("needs a second, destructive confirmation before deleting", async () => {
    const tree = await mount();
    await press(tree, "open-delete");
    await press(tree, "confirm-delete");

    expect(deleteAccount).not.toHaveBeenCalled();
    const [, , buttons] = alertSpy.mock.calls.at(-1)!;
    expect(buttons?.find((b) => b.text === "탈퇴하기")?.style).toBe("destructive");
    expect(buttons?.find((b) => b.text === "취소")?.style).toBe("cancel");

    await tapAlertButton("탈퇴하기");
    expect(deleteAccount).toHaveBeenCalledTimes(1);
  });

  it("keeps the account when the sheet's primary action is pressed", async () => {
    const tree = await mount();
    await press(tree, "open-delete");
    const keep = tree.root.findAll(
      (n) => n.props.label === "계정 유지하기" && !!n.props.onPress,
    )[0];
    await act(async () => keep.props.onPress());

    expect(tree.root.findAllByProps({ testID: "delete-confirm" })).toHaveLength(0);
    expect(deleteAccount).not.toHaveBeenCalled();
  });

  it("explains an expired session by error code, not message", async () => {
    deleteAccount.mockRejectedValueOnce(new AppError("AUTH_TOKEN_INVALID", "boom", 401));
    const tree = await mount();

    await press(tree, "open-delete");
    await press(tree, "confirm-delete");
    await tapAlertButton("탈퇴하기");

    expect(texts(tree).join("|")).toContain("로그인이 만료됐어요");
  });

  it("logs out through the auth store", async () => {
    const tree = await mount();
    await press(tree, "logout");
    expect(logout).toHaveBeenCalledTimes(1);
  });

  it("asks a guest to log in instead of showing account rows", async () => {
    useAuthStore.setState({ user: null, isAuthenticated: false, accessToken: null });
    const tree = await mount();
    expect(tree.root.findAllByProps({ testID: "account-guest" }).length).toBeGreaterThan(0);
    expect(tree.root.findAllByProps({ testID: "open-delete" })).toHaveLength(0);
  });
});
