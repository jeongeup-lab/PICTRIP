import { create } from "zustand";

export type AuthReason = "save" | "saved-list";

interface AuthPromptState {
  visible: boolean;
  reason: AuthReason | null;
  resolve: ((ok: boolean) => void) | null;
  prompt: (reason: AuthReason) => Promise<boolean>;
  succeed: () => void;
  hide: () => void;
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
  // Close the sheet UI but KEEP the pending action armed — used when handing off
  // to the email screen (a separate route that logs in and resolves the pending
  // action later via the isAuthenticated watcher in AuthPromptSheet). Pushing a
  // route while the native <Modal> is open would render it behind the sheet.
  hide: () => set({ visible: false }),
  dismiss: () => {
    get().resolve?.(false);
    set({ visible: false, reason: null, resolve: null });
  },
}));
