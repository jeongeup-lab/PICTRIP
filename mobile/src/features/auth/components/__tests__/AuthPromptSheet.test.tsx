import renderer, { act } from "react-test-renderer";
import { AuthPromptSheet } from "@/features/auth/components/AuthPromptSheet";
import { useAuthPromptStore } from "@/features/auth/stores/auth-prompt-store";
import { useAuthStore } from "@/features/auth/stores/auth-store";

// LoginCard pulls in native social/OAuth deps — not under test here.
jest.mock("@/features/auth/components/LoginCard", () => ({ LoginCard: () => null }));
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
jest.mock("expo-router", () => ({ router: { push: jest.fn() } }));

const setAuth = (isAuthenticated: boolean) => useAuthStore.setState({ isAuthenticated });

describe("AuthPromptSheet", () => {
  let tree: renderer.ReactTestRenderer | null = null;

  beforeEach(() => {
    useAuthPromptStore.setState({ visible: false, reason: null, resolve: null });
    setAuth(false);
  });

  afterEach(() => {
    act(() => tree?.unmount());
    tree = null;
  });

  it("resumes the pending action when auth succeeds via the email screen path", async () => {
    await act(async () => {
      tree = renderer.create(<AuthPromptSheet />);
    });

    // Guest taps save → a pending prompt is armed and the sheet shows.
    let resolved: boolean | null = null;
    let pending!: Promise<boolean>;
    act(() => {
      pending = useAuthPromptStore.getState().prompt("save");
    });
    void pending.then((v) => (resolved = v));
    expect(useAuthPromptStore.getState().visible).toBe(true);

    // "이메일로 계속하기": the Modal closes but the action stays armed, then the
    // email screen logs in on its own route → isAuthenticated flips.
    act(() => useAuthPromptStore.getState().hide());
    expect(useAuthPromptStore.getState().visible).toBe(false);
    await act(async () => setAuth(true));

    await act(async () => {}); // flush the resolve microtask
    expect(resolved).toBe(true); // pending save resumes
    expect(useAuthPromptStore.getState().resolve).toBeNull();
  });

  it("does nothing when no action is pending", async () => {
    await act(async () => {
      tree = renderer.create(<AuthPromptSheet />);
    });
    await act(async () => setAuth(true));
    expect(useAuthPromptStore.getState().resolve).toBeNull();
  });
});
