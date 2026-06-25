import * as SecureStore from "expo-secure-store";
import { File } from "expo-file-system";
import {
  getOnboardingSeen,
  setOnboardingSeen,
  getRefreshToken,
  setRefreshToken,
  clearRefreshToken,
  ensureFreshInstall,
} from "@/lib/storage";

describe("storage", () => {
  beforeEach(() => jest.clearAllMocks());

  it("reports onboarding unseen when flag absent", async () => {
    (SecureStore.getItemAsync as jest.Mock).mockResolvedValue(null);
    expect(await getOnboardingSeen()).toBe(false);
  });

  it("reports onboarding seen when flag present", async () => {
    (SecureStore.getItemAsync as jest.Mock).mockResolvedValue("1");
    expect(await getOnboardingSeen()).toBe(true);
  });

  it("writes onboarding flag", async () => {
    await setOnboardingSeen();
    expect(SecureStore.setItemAsync).toHaveBeenCalledWith("onboarding_seen", "1");
  });

  it("round-trips refresh token", async () => {
    await setRefreshToken("abc");
    expect(SecureStore.setItemAsync).toHaveBeenCalledWith(
      "refresh_token",
      "abc",
      expect.objectContaining({ keychainAccessible: "WHEN_UNLOCKED_THIS_DEVICE_ONLY" }),
    );
    (SecureStore.getItemAsync as jest.Mock).mockResolvedValue("abc");
    expect(await getRefreshToken()).toBe("abc");
    await clearRefreshToken();
    expect(SecureStore.deleteItemAsync).toHaveBeenCalledWith("refresh_token");
  });

  describe("ensureFreshInstall", () => {
    it("clears the onboarding flag and writes the marker on a fresh install", async () => {
      const create = jest.fn();
      (File as unknown as jest.Mock).mockImplementation(() => ({ exists: false, create }));
      await ensureFreshInstall();
      expect(SecureStore.deleteItemAsync).toHaveBeenCalledWith("onboarding_seen");
      expect(create).toHaveBeenCalled();
    });

    it("does nothing when the install marker already exists", async () => {
      const create = jest.fn();
      (File as unknown as jest.Mock).mockImplementation(() => ({ exists: true, create }));
      await ensureFreshInstall();
      expect(SecureStore.deleteItemAsync).not.toHaveBeenCalled();
      expect(create).not.toHaveBeenCalled();
    });

    it("never throws when the filesystem is unavailable", async () => {
      (File as unknown as jest.Mock).mockImplementation(() => {
        throw new Error("no fs");
      });
      await expect(ensureFreshInstall()).resolves.toBeUndefined();
      expect(SecureStore.deleteItemAsync).not.toHaveBeenCalled();
    });
  });
});
