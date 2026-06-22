import { create } from "zustand";
import { bareClient } from "@/lib/bare-client";
import type { TokenPair, User } from "@/lib/api-types";
import { getRefreshToken, setRefreshToken, clearRefreshToken } from "@/lib/storage";
import { AppError } from "@/lib/app-error";

interface AuthState {
  accessToken: string | null;
  user: User | null;
  isAuthenticated: boolean;
  setSession: (pair: TokenPair) => Promise<void>;
  refresh: () => Promise<string>;
  clear: () => Promise<void>;
  hydrate: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  accessToken: null,
  user: null,
  isAuthenticated: false,

  setSession: async (pair) => {
    await setRefreshToken(pair.refreshToken);
    set({ accessToken: pair.accessToken, user: pair.user, isAuthenticated: true });
  },

  refresh: async () => {
    const refreshToken = await getRefreshToken();
    if (!refreshToken) {
      await get().clear();
      throw new AppError("AUTH_TOKEN_INVALID", "로그인이 필요합니다.", 401);
    }
    try {
      const pair = (await bareClient.post("/auth/refresh", {
        refreshToken,
      })) as unknown as TokenPair;
      await get().setSession(pair);
      return pair.accessToken;
    } catch (e) {
      await get().clear();
      throw e;
    }
  },

  clear: async () => {
    await clearRefreshToken();
    set({ accessToken: null, user: null, isAuthenticated: false });
  },

  hydrate: async () => {
    const refreshToken = await getRefreshToken();
    if (!refreshToken) return;
    try {
      await get().refresh();
    } catch {
      // quiet guest demotion — no toast, no retry (S1)
    }
  },
}));
