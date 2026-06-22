import { useAuthStore } from "@/features/auth/stores/auth-store";
import { bareClient } from "@/lib/bare-client";
import * as storage from "@/lib/storage";
import { getIdToken } from "@/features/auth/usecases/oauth-providers";
import { recordConsentSnapshot } from "@/features/auth/usecases/record-consent";
import { oauthLogin, logoutRequest, deleteAccountRequest } from "@/features/auth/api";
import { AppError } from "@/lib/app-error";

jest.mock("@/lib/bare-client", () => ({ bareClient: { post: jest.fn() } }));
jest.mock("@/lib/storage");
jest.mock("@/features/auth/usecases/oauth-providers", () => ({ getIdToken: jest.fn() }));
jest.mock("@/features/auth/usecases/record-consent", () => ({
  recordConsentSnapshot: jest.fn(),
}));
jest.mock("@/features/auth/api", () => ({
  oauthLogin: jest.fn(),
  logoutRequest: jest.fn(),
  deleteAccountRequest: jest.fn(),
}));

const pair = {
  accessToken: "acc",
  refreshToken: "ref",
  expiresIn: 900,
  user: {
    id: 1,
    displayName: "U",
    email: null,
    avatarUrl: null,
    isOnboarded: false,
    createdAt: null,
  },
};

describe("auth-store", () => {
  beforeEach(async () => {
    jest.clearAllMocks();
    await useAuthStore.getState().clear();
  });

  it("setSession puts access token in memory and persists refresh", async () => {
    await useAuthStore.getState().setSession(pair as never);
    expect(useAuthStore.getState().accessToken).toBe("acc");
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
    expect(storage.setRefreshToken).toHaveBeenCalledWith("ref");
  });

  it("refresh updates the session and returns the new access token", async () => {
    (storage.getRefreshToken as jest.Mock).mockResolvedValue("ref");
    (bareClient.post as jest.Mock).mockResolvedValue({
      ...pair,
      accessToken: "acc2",
      refreshToken: "ref2",
    });
    const token = await useAuthStore.getState().refresh();
    expect(token).toBe("acc2");
    expect(useAuthStore.getState().accessToken).toBe("acc2");
    expect(storage.setRefreshToken).toHaveBeenCalledWith("ref2");
  });

  it("refresh clears the session and throws when no refresh token", async () => {
    (storage.getRefreshToken as jest.Mock).mockResolvedValue(null);
    await expect(useAuthStore.getState().refresh()).rejects.toThrow();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it("hydrate returns early when no refresh token (no refresh attempt)", async () => {
    (storage.getRefreshToken as jest.Mock).mockResolvedValue(null);
    await expect(useAuthStore.getState().hydrate()).resolves.toBeUndefined();
    expect(bareClient.post).not.toHaveBeenCalled();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it("hydrate swallows a failing refresh and clears the session", async () => {
    (storage.getRefreshToken as jest.Mock).mockResolvedValue("ref");
    (bareClient.post as jest.Mock).mockRejectedValue(new Error("boom"));
    await expect(useAuthStore.getState().hydrate()).resolves.toBeUndefined();
    expect(bareClient.post).toHaveBeenCalled();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });
});

describe("auth-store P3 actions", () => {
  beforeEach(async () => {
    jest.clearAllMocks();
    (recordConsentSnapshot as jest.Mock).mockResolvedValue(undefined);
    await useAuthStore.getState().clear();
  });

  it("loginWithOAuth success sets the session and records consent", async () => {
    (getIdToken as jest.Mock).mockResolvedValue({ idToken: "t", nonce: "n" });
    (oauthLogin as jest.Mock).mockResolvedValue(pair);
    const res = await useAuthStore.getState().loginWithOAuth("kakao");
    expect(res).toBe("success");
    expect(oauthLogin).toHaveBeenCalledWith("kakao", "t", "n");
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
    expect(useAuthStore.getState().user?.id).toBe(1);
    expect(recordConsentSnapshot).toHaveBeenCalled();
  });

  it("loginWithOAuth returns 'canceled' without calling the backend", async () => {
    (getIdToken as jest.Mock).mockResolvedValue("canceled");
    expect(await useAuthStore.getState().loginWithOAuth("apple")).toBe("canceled");
    expect(oauthLogin).not.toHaveBeenCalled();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it("loginWithOAuth propagates AppError from the backend", async () => {
    (getIdToken as jest.Mock).mockResolvedValue({ idToken: "t" });
    (oauthLogin as jest.Mock).mockRejectedValue(new AppError("OAUTH_ID_TOKEN_INVALID", "x", 401));
    await expect(useAuthStore.getState().loginWithOAuth("google")).rejects.toBeInstanceOf(AppError);
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it("logout clears the session even if the request fails", async () => {
    await useAuthStore.getState().setSession(pair as never);
    (logoutRequest as jest.Mock).mockRejectedValue(new Error("net"));
    await useAuthStore.getState().logout();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it("deleteAccount clears the session on success", async () => {
    await useAuthStore.getState().setSession(pair as never);
    (deleteAccountRequest as jest.Mock).mockResolvedValue(undefined);
    await useAuthStore.getState().deleteAccount();
    expect(deleteAccountRequest).toHaveBeenCalled();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it("devLogin sets a fake in-memory session", () => {
    useAuthStore.getState().devLogin();
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
    expect(useAuthStore.getState().accessToken).toBeTruthy();
  });
});
