import { create } from "zustand";
import { bareClient } from "@/lib/bare-client";
import type { TokenPair, User } from "@/lib/api-types";
import { getRefreshToken, setRefreshToken, clearRefreshToken } from "@/lib/storage";
import { AppError } from "@/lib/app-error";
import { registerAuthSession } from "@/lib/auth-session";
import { getIdToken, type Provider } from "@/features/auth/usecases/oauth-providers";
import { recordConsentSnapshot } from "@/features/auth/usecases/record-consent";
import { oauthLogin, logoutRequest, deleteAccountRequest } from "@/features/auth/api";
import { queryClient } from "@/lib/query-client";
import { useRecentSpots } from "@/features/spots/stores/recent-store";

interface AuthState {
  accessToken: string | null;
  user: User | null;
  isAuthenticated: boolean;
  setSession: (pair: TokenPair) => Promise<void>;
  refresh: () => Promise<string>;
  clear: () => Promise<void>;
  hydrate: () => Promise<void>;
  loginWithOAuth: (provider: Provider) => Promise<"success" | "canceled">;
  logout: () => Promise<void>;
  deleteAccount: () => Promise<void>;
  devLogin: () => void;
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
    queryClient.removeQueries({ queryKey: ["saved"] });
    queryClient.removeQueries({ queryKey: ["consents"] });
    useRecentSpots.getState().clear();
  },

  hydrate: async () => {
    const refreshToken = await getRefreshToken();
    if (!refreshToken) return;
    try {
      await get().refresh();
    } catch {}
  },

  loginWithOAuth: async (provider) => {
    const outcome = await getIdToken(provider);
    if (outcome === "canceled") return "canceled";
    const pair = await oauthLogin(provider, outcome.idToken, outcome.nonce);
    await get().setSession(pair);
    void recordConsentSnapshot().catch(() => undefined);
    return "success";
  },

  logout: async () => {
    const refreshToken = await getRefreshToken();
    try {
      await logoutRequest(refreshToken);
    } catch {}
    await get().clear();
  },

  deleteAccount: async () => {
    await deleteAccountRequest(await getRefreshToken());
    await get().clear();
  },

  devLogin: () => {
    const user: User = {
      id: 0,
      displayName: "개발자",
      email: "dev@pictrip.local",
      avatarUrl: null,
      isOnboarded: true,
      createdAt: null,
    };
    set({ accessToken: "dev-access-token", user, isAuthenticated: true });
  },
}));

registerAuthSession({
  getAccessToken: () => useAuthStore.getState().accessToken,
  refresh: () => useAuthStore.getState().refresh(),
  clear: () => useAuthStore.getState().clear(),
});
