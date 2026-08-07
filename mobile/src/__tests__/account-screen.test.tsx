import renderer, { act } from "react-test-renderer";
import { Text } from "react-native";
import AccountScreen from "@/app/account";
import { useAuthStore } from "@/features/auth/stores/auth-store";
import { useSavedList } from "@/features/saved/queries";
import { AppError } from "@/lib/app-error";
import type { User } from "@/lib/api-types";

jest.mock("expo-router", () => ({ router: { push: jest.fn(), back: jest.fn() } }));
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
jest.mock("@/features/saved/queries", () => ({ useSavedList: jest.fn() }));

const useSavedListMock = useSavedList as jest.Mock;
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
  useSavedListMock.mockReturnValue({ data: [{ contentId: "1" }, { contentId: "2" }] });
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

  it("asks for confirmation with a delete checklist before deleting", async () => {
    const tree = await mount();
    expect(tree.root.findAllByProps({ testID: "delete-confirm" })).toHaveLength(0);

    await press(tree, "open-delete");
    expect(texts(tree).join("|")).toContain("스크랩 2곳");
    expect(deleteAccount).not.toHaveBeenCalled();

    await press(tree, "confirm-delete");
    expect(deleteAccount).toHaveBeenCalledTimes(1);
  });

  it("explains an expired session by error code, not message", async () => {
    deleteAccount.mockRejectedValueOnce(new AppError("AUTH_TOKEN_INVALID", "boom", 401));
    const tree = await mount();

    await press(tree, "open-delete");
    await press(tree, "confirm-delete");

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
