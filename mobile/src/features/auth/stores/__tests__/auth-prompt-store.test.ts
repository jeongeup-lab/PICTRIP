import { useAuthPromptStore } from "@/features/auth/stores/auth-prompt-store";

describe("auth-prompt-store", () => {
  beforeEach(() => useAuthPromptStore.setState({ visible: false, reason: null, resolve: null }));

  it("prompt opens the sheet and resolves true on succeed", async () => {
    const p = useAuthPromptStore.getState().prompt("save");
    expect(useAuthPromptStore.getState().visible).toBe(true);
    expect(useAuthPromptStore.getState().reason).toBe("save");
    useAuthPromptStore.getState().succeed();
    await expect(p).resolves.toBe(true);
    expect(useAuthPromptStore.getState().visible).toBe(false);
  });

  it("prompt resolves false on dismiss", async () => {
    const p = useAuthPromptStore.getState().prompt("saved-list");
    useAuthPromptStore.getState().dismiss();
    await expect(p).resolves.toBe(false);
    expect(useAuthPromptStore.getState().resolve).toBeNull();
  });
});
