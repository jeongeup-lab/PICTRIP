import * as SecureStore from "expo-secure-store";
import { File, Paths } from "expo-file-system";

const REFRESH_KEY = "refresh_token";
const ONBOARDING_KEY = "onboarding_seen";
const INSTALL_MARKER = "install.marker";

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

/**
 * iOS keychain entries survive an app uninstall, so the secure-store
 * `onboarding_seen` flag would otherwise persist across a fresh reinstall and
 * the onboarding flow would never appear again (the reported "온보딩이 사라짐"
 * symptom). The app's document directory IS wiped on uninstall, so we keep a
 * marker file there to detect a fresh install: if the marker is absent this is
 * a new install — clear the stale onboarding flag, then drop the marker so
 * later launches within the same install skip the reset. Everything is wrapped
 * so any FileSystem failure silently falls back to the prior behavior and never
 * blocks boot. The refresh token is cleared too: the keychain entry also
 * survives uninstall, so a reinstaller would otherwise be silently hydrated into
 * the previous install's session.
 */
export async function ensureFreshInstall(): Promise<void> {
  try {
    const marker = new File(Paths.document, INSTALL_MARKER);
    if (marker.exists) return;
    try {
      await SecureStore.deleteItemAsync(ONBOARDING_KEY);
      await clearRefreshToken();
    } catch {
      // Leave the entries as-is if they can't be cleared.
    }
    marker.create();
  } catch {
    // FileSystem unavailable — fall back to existing behavior.
  }
}
