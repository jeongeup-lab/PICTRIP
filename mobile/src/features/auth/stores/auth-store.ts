import { create } from "zustand";
import { bareClient } from "@/lib/bare-client";
import type { TokenPair, User } from "@/lib/api-types";
import { getRefreshToken, setRefreshToken, clearRefreshToken } from "@/lib/storage";
import { AppError } from "@/lib/app-error";
import { getIdToken, type Provider } from "@/features/auth/usecases/oauth-providers";
import { recordConsentSnapshot } from "@/features/auth/usecases/record-consent";
import {
  oauthLogin,
  emailLogin,
  emailSignup,
  logoutRequest,
  deleteAccountRequest,
} from "@/features/auth/api";
import { queryClient } from "@/lib/query-client";

interface AuthState {
  accessToken: string | null;
  user: User | null;
  isAuthenticated: boolean;
  setSession: (pair: TokenPair) => Promise<void>;
  refresh: () => Promise<string>;
  clear: () => Promise<void>;
  hydrate: () => Promise<void>;
  loginWithOAuth: (provider: Provider) => Promise<"success" | "canceled">;
  loginWithEmail: (email: string, password: string) => Promise<void>;
  signupWithEmail: (email: string, password: string, name?: string) => Promise<void>;
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
    // Evict the previous user's saved/scrap list so a different user (or guest)
    // never sees stale cached data. Key inlined (not imported from
    // saved/queries) to avoid the auth-store ↔ saved/queries import cycle —
    // MUST stay in sync with savedKeys.list (["saved"]).
    queryClient.removeQueries({ queryKey: ["saved"] });
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

  loginWithOAuth: async (provider) => {
    const outcome = await getIdToken(provider);
    if (outcome === "canceled") return "canceled";
    const pair = await oauthLogin(provider, outcome.idToken, outcome.nonce);
    await get().setSession(pair);
    // Consent is best-effort — never block login on it (S01 §3).
    void recordConsentSnapshot().catch(() => undefined);
    return "success";
  },

  loginWithEmail: async (email, password) => {
    const pair = await emailLogin(email, password);
    await get().setSession(pair);
    // Consent is best-effort — never block login on it (S01 §3).
    void recordConsentSnapshot().catch(() => undefined);
  },

  signupWithEmail: async (email, password, name) => {
    const pair = await emailSignup(email, password, name);
    await get().setSession(pair);
    // Consent is best-effort — never block signup on it (S01 §3).
    void recordConsentSnapshot().catch(() => undefined);
  },

  logout: async () => {
    const refreshToken = await getRefreshToken();
    try {
      await logoutRequest(refreshToken);
    } catch {
      // Logout is local-authoritative; server denylist is best-effort.
    }
    await get().clear();
  },

  deleteAccount: async () => {
    await deleteAccountRequest();
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
    // __DEV__ smoke only — no backend call, no refresh persisted.
    set({ accessToken: "dev-access-token", user, isAuthenticated: true });
  },
}));
