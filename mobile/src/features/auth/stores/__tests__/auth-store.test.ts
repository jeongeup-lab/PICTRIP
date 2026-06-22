import { useAuthStore } from "@/features/auth/stores/auth-store";
import { bareClient } from "@/lib/bare-client";
import * as storage from "@/lib/storage";

jest.mock("@/lib/bare-client", () => ({ bareClient: { post: jest.fn() } }));
jest.mock("@/lib/storage");

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
