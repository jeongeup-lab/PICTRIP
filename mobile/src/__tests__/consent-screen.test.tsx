import renderer, { act } from "react-test-renderer";
import { Text } from "react-native";
import ConsentScreen from "@/app/consent";
import { useAuthStore } from "@/features/auth/stores/auth-store";
import type { User } from "@/lib/api-types";

jest.mock("expo-router", () => ({
  router: { back: jest.fn(), canGoBack: jest.fn(), replace: jest.fn() },
  useFocusEffect: (effect: () => void | (() => void)) =>
    jest.requireActual<typeof import("react")>("react").useEffect(effect, [effect]),
}));
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
jest.mock("@/features/consent/queries", () => ({
  useConsents: jest.fn(),
  useUpdateConsent: jest.fn(() => ({ mutate: jest.fn() })),
}));
jest.mock("expo-location", () => ({
  getForegroundPermissionsAsync: jest.fn(async () => ({ granted: true })),
}));

const useConsentsMock = jest.requireMock<{ useConsents: jest.Mock }>(
  "@/features/consent/queries",
).useConsents;

const USER: User = {
  id: 7,
  displayName: "이신성",
  email: "sinseong@example.com",
  avatarUrl: null,
  isOnboarded: true,
  createdAt: "2026-03-14T09:00:00Z",
};

let holder: renderer.ReactTestRenderer | null = null;

beforeEach(() => {
  useAuthStore.setState({ user: USER, isAuthenticated: true, accessToken: "token" });
  useConsentsMock.mockReturnValue({
    data: {
      locationConsent: true,
      termsVersion: "2026-06-22",
      consentedAt: "2026-03-14T09:00:00Z",
    },
    isLoading: false,
    isError: false,
    refetch: jest.fn(),
  });
});

afterEach(async () => {
  jest.clearAllMocks();
  await act(async () => {
    holder?.unmount();
  });
});

describe("ConsentScreen", () => {
  it("renders the two consent records as read-only statuses", async () => {
    const tree: { tree: renderer.ReactTestRenderer | null } = { tree: null };
    await act(async () => {
      tree.tree = renderer.create(<ConsentScreen />);
    });

    if (tree.tree === null) throw new Error("screen did not mount");
    holder = tree.tree;
    const shown = tree.tree.root
      .findAllByType(Text)
      .map((node) => JSON.stringify(node.props.children))
      .join("|");
    expect(shown).toContain("[필수] 약관·개인정보 수집·이용");
    expect(shown).toContain("[선택] 위치정보 수집·이용");
    expect(shown).not.toContain("재동의");
    expect(shown).not.toContain("버전");
  });

  it("shows an unavailable status without exposing version or date copy", async () => {
    useConsentsMock.mockReturnValue({
      data: { locationConsent: false, termsVersion: null, consentedAt: null },
      isLoading: false,
      isError: false,
      refetch: jest.fn(),
    });
    const tree: { tree: renderer.ReactTestRenderer | null } = { tree: null };
    await act(async () => {
      tree.tree = renderer.create(<ConsentScreen />);
    });
    if (tree.tree === null) throw new Error("screen did not mount");
    holder = tree.tree;
    const shown = tree.tree.root
      .findAllByType(Text)
      .map((node) => JSON.stringify(node.props.children))
      .join("|");
    expect(shown).toContain("기록 없음");
    expect(shown).toContain("동의 안 함");
    expect(shown).not.toContain("2026");
  });

  it("guides guests to log in instead of showing consent records", async () => {
    await act(async () => {
      useAuthStore.setState({ user: null, isAuthenticated: false, accessToken: null });
    });
    const tree: { tree: renderer.ReactTestRenderer | null } = { tree: null };
    await act(async () => {
      tree.tree = renderer.create(<ConsentScreen />);
    });
    if (tree.tree === null) throw new Error("screen did not mount");
    holder = tree.tree;
    const shown = tree.tree.root
      .findAllByType(Text)
      .map((node) => JSON.stringify(node.props.children))
      .join("|");
    expect(shown).toContain("로그인이 필요해요");
    expect(shown).not.toContain("[필수] 약관·개인정보 수집·이용");
  });
});
