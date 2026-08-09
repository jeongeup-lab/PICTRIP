import renderer, { act } from "react-test-renderer";
import { AuthPromptSheet } from "@/features/auth/components/AuthPromptSheet";
import { useAuthPromptStore } from "@/features/auth/stores/auth-prompt-store";
import { useAuthStore } from "@/features/auth/stores/auth-store";

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

  it("resumes the pending action once the sheet's login succeeds", async () => {
    await act(async () => {
      tree = renderer.create(<AuthPromptSheet />);
    });

    let resolved: boolean | null = null;
    let pending!: Promise<boolean>;
    act(() => {
      pending = useAuthPromptStore.getState().prompt("save");
    });
    void pending.then((v) => (resolved = v));
    expect(useAuthPromptStore.getState().visible).toBe(true);

    await act(async () => setAuth(true));

    await act(async () => {});
    expect(resolved).toBe(true);
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
