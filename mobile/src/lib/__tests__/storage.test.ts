import * as SecureStore from "expo-secure-store";
import {
  getOnboardingSeen,
  setOnboardingSeen,
  getRefreshToken,
  setRefreshToken,
  clearRefreshToken,
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
});
