import * as SecureStore from "expo-secure-store";
import { File, Paths } from "expo-file-system";

const REFRESH_KEY = "refresh_token";
const ONBOARDING_KEY = "onboarding_seen";
const SEEN_CHANNELS_KEY = "seen_channels";
const AI_OPT_OUT_KEY = "ai_opt_out";
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

export async function getAiOptOut(): Promise<boolean> {
  return (await SecureStore.getItemAsync(AI_OPT_OUT_KEY)) === "1";
}

export async function setAiOptOut(optedOut: boolean): Promise<void> {
  if (optedOut) await SecureStore.setItemAsync(AI_OPT_OUT_KEY, "1");
  else await SecureStore.deleteItemAsync(AI_OPT_OUT_KEY);
}

export async function getSeenChannelsRaw(): Promise<string | null> {
  return SecureStore.getItemAsync(SEEN_CHANNELS_KEY);
}

export async function setSeenChannelsRaw(value: string): Promise<void> {
  await SecureStore.setItemAsync(SEEN_CHANNELS_KEY, value);
}

export async function ensureFreshInstall(): Promise<void> {
  try {
    const marker = new File(Paths.document, INSTALL_MARKER);
    if (marker.exists) return;
    try {
      await SecureStore.deleteItemAsync(ONBOARDING_KEY);
      await clearRefreshToken();
    } catch {}
    marker.create();
  } catch {}
}
