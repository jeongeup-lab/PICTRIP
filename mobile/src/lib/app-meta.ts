import Constants from "expo-constants";
import * as Updates from "expo-updates";

const APP_VERSION = Constants.expoConfig?.version ?? "0.0.0";

export const EMBEDDED_BUNDLE_LABEL = "내장";

export function bundleLabel(updateId: string | null): string {
  return updateId ? updateId.slice(0, 8) : EMBEDDED_BUNDLE_LABEL;
}

export const APP_BUILD_LABEL = `${APP_VERSION} · ${bundleLabel(Updates.updateId ?? null)}`;
