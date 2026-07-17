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

export const useAuthPromptStore = create<AuthPromptState>((set, get) => ({
  visible: false,
  reason: null,
  resolve: null,
  prompt: (reason) => new Promise<boolean>((resolve) => set({ visible: true, reason, resolve })),
  succeed: () => {
    get().resolve?.(true);
    set({ visible: false, reason: null, resolve: null });
  },
  hide: () => set({ visible: false }),
  dismiss: () => {
    get().resolve?.(false);
    set({ visible: false, reason: null, resolve: null });
  },
}));
