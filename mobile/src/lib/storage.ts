import * as SecureStore from "expo-secure-store";

const REFRESH_KEY = "refresh_token";
const ONBOARDING_KEY = "onboarding_seen";

const refreshOptions = {
  keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
};

export async function getRefreshToken(): Promise<string | null> {
  return SecureStore.getItemAsync(REFRESH_KEY);
}

export async function setRefreshToken(token: string): Promise<void> {
  await SecureStore.setItemAsync(REFRESH_KEY, token, refreshOptions);
}

export async function clearRefreshToken(): Promise<void> {
  await SecureStore.deleteItemAsync(REFRESH_KEY);
}

export async function getOnboardingSeen(): Promise<boolean> {
  return (await SecureStore.getItemAsync(ONBOARDING_KEY)) === "1";
}

export async function setOnboardingSeen(): Promise<void> {
  await SecureStore.setItemAsync(ONBOARDING_KEY, "1");
}
