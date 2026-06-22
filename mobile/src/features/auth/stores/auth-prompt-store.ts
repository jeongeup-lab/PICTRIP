import { create } from "zustand";

export type AuthReason = "save" | "saved-list";

interface AuthPromptState {
  visible: boolean;
  reason: AuthReason | null;
  resolve: ((ok: boolean) => void) | null;
  prompt: (reason: AuthReason) => Promise<boolean>;
  succeed: () => void;
  dismiss: () => void;
}

/** Imperative login-nudge gate. `prompt()` opens the root sheet and returns a
 * promise that resolves true (logged in) or false (dismissed) so callers can
 * resume the pending action (S01 §3 보류 액션 재개). */
export const useAuthPromptStore = create<AuthPromptState>((set, get) => ({
  visible: false,
  reason: null,
  resolve: null,
  prompt: (reason) => new Promise<boolean>((resolve) => set({ visible: true, reason, resolve })),
  succeed: () => {
    get().resolve?.(true);
    set({ visible: false, reason: null, resolve: null });
  },
  dismiss: () => {
    get().resolve?.(false);
    set({ visible: false, reason: null, resolve: null });
  },
}));
